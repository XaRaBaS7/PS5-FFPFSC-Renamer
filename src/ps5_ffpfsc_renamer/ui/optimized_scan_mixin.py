from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from ..cache_batch import lookup_cache_batch
from ..ffpfsc_reader import MetadataReadCancelled, MetadataReadError, read_metadata
from ..metadata import GameMetadata
from ..root_health import RootStatus, probe_root, root_key
from ..scan_profile import ScanProfile
from ..scanner import collapse_nested_roots, scan_ffpfsc


def _record_configured_root_status(
    statuses: dict[str, RootStatus],
    configured_root: Path,
    status: RootStatus,
) -> None:
    """Store probe state under the root identity selected by the user."""

    statuses[root_key(configured_root)] = status


def _mark_effective_root_error(
    statuses: dict[str, RootStatus],
    probes: list[tuple[Path, RootStatus]],
    effective_root: Path,
    detail: str,
) -> tuple[Path, ...]:
    """Map one discovery failure back to every configured root it covered."""

    affected: list[Path] = []
    for configured_root, status in probes:
        if not status.available:
            continue
        try:
            status.path.relative_to(effective_root)
        except ValueError:
            continue
        statuses[root_key(configured_root)] = RootStatus(status.path, "ERROR", detail)
        affected.append(configured_root)

    if not affected:
        statuses[root_key(effective_root)] = RootStatus(effective_root, "ERROR", detail)
        affected.append(effective_root)
    return tuple(affected)


class OptimizedScanMixin:
    """Batch discovery/cache-aware metadata scan for the canonical desktop."""

    def _scan_worker(self, folder: Path, recursive: bool, worker_setting: str) -> None:
        started_at = time.monotonic()
        selected_roots = list(self.library_roots) or [folder]
        unavailable: list[str] = []
        accessible_roots: list[Path] = []
        root_statuses: dict[str, RootStatus] = {}
        probed_roots: list[tuple[Path, RootStatus]] = []

        probe_started = time.monotonic()
        # Probe on the worker thread so a sleeping NAS/share never blocks Tk.
        for root in selected_roots:
            configured_root = Path(root)
            status = probe_root(configured_root)
            probed_roots.append((configured_root, status))
            _record_configured_root_status(root_statuses, configured_root, status)
            if not status.available:
                unavailable.append(
                    f"{configured_root} — {status.detail or status.state.lower()}"
                )
                continue
            accessible_roots.append(status.path)
        root_probe_seconds = time.monotonic() - probe_started

        self._root_statuses = root_statuses
        self._last_unavailable_roots = tuple(unavailable)
        try:
            self.after(0, self._update_root_summary)
        except Exception:
            pass

        if not accessible_roots and selected_roots:
            detail = "No selected library root is currently accessible."
            if unavailable:
                detail += "\n\n" + "\n".join(unavailable[:10])
            self.after(0, lambda text=detail: self._scan_failed(text))
            return

        effective_roots = (
            collapse_nested_roots(accessible_roots) if recursive else accessible_roots
        )
        self._last_collapsed_root_count = max(0, len(accessible_roots) - len(effective_roots))

        discovery_started = time.monotonic()
        images: list[Path] = []
        seen: set[str] = set()
        for root in effective_roots:
            try:
                discovered = scan_ffpfsc(root, recursive=recursive)
            except Exception as exc:
                affected = _mark_effective_root_error(
                    root_statuses,
                    probed_roots,
                    root,
                    str(exc),
                )
                unavailable.extend(f"{configured} — {exc}" for configured in affected)
                continue
            for image in discovered:
                # scan_ffpfsc already returns absolute paths. Avoid another
                # resolve/stat round trip here; casefolded path text is enough
                # for duplicate suppression across overlapping selections.
                key = str(image).casefold()
                if key in seen:
                    continue
                seen.add(key)
                images.append(image)

        images.sort(key=lambda path: str(path).casefold())
        discovery_seconds = time.monotonic() - discovery_started

        self._root_statuses = root_statuses
        self._last_unavailable_roots = tuple(unavailable)
        try:
            self.after(0, self._update_root_summary)
        except Exception:
            pass

        total = len(images)
        self.after(0, lambda: self.files_var.set(str(total)))

        cache_started = time.monotonic()
        self._last_scan_file_states = {}
        try:
            cache_batch = lookup_cache_batch(self.cache, images)
            verified_lookups = cache_batch.verified
            failure_lookups = cache_batch.failures
            self._last_scan_file_states = dict(cache_batch.file_states)
        except Exception:
            # Cache is only an acceleration layer. A damaged or temporarily
            # locked cache must never prevent a library scan.
            verified_lookups = {}
            failure_lookups = {}
        cache_seconds = time.monotonic() - cache_started

        cached_items: list[tuple[Path, GameMetadata]] = []
        cached_errors: list[tuple[Path, str]] = []
        misses: list[Path] = []

        for index, image in enumerate(images, start=1):
            if self.cancel_event.is_set():
                self.after(0, lambda: self._scan_cancelled(index - 1, total))
                return

            verified = verified_lookups.get(image)
            if verified is not None and verified.hit and verified.metadata is not None:
                cached_items.append((image, verified.metadata))
            else:
                failed = failure_lookups.get(image)
                if failed is not None and failed.hit and failed.error:
                    cached_errors.append((image, failed.error))
                else:
                    misses.append(image)

            cached_count = len(cached_items) + len(cached_errors)
            self.after(
                0,
                lambda done=index, hits=cached_count, new=len(misses): self._cache_check_progress(
                    done, total, hits, new
                ),
            )

        cache_hits = len(cached_items) + len(cached_errors)
        self._last_failure_cache_hits = len(cached_errors)
        self._last_batch_cache_files = total
        workers = self._resolve_worker_count(worker_setting, len(misses))
        self.after(0, lambda: self._analysis_started(total, cache_hits, len(misses), workers))

        parsed = list(cached_items)
        errors = list(cached_errors)
        completed = cache_hits
        mkpfs_reads = 0

        def set_profile(mkpfs_seconds: float) -> None:
            self._last_scan_profile = ScanProfile(
                total_files=total,
                selected_roots=len(selected_roots),
                effective_roots=len(effective_roots),
                unavailable_roots=len(unavailable),
                cache_hits=cache_hits,
                failure_cache_hits=len(cached_errors),
                mkpfs_reads=mkpfs_reads,
                workers=workers,
                root_probe_seconds=root_probe_seconds,
                discovery_seconds=discovery_seconds,
                cache_seconds=cache_seconds,
                mkpfs_seconds=mkpfs_seconds,
                total_seconds=time.monotonic() - started_at,
            )

        if not misses:
            set_profile(0.0)
            self.after(
                0,
                lambda: self._scan_complete(
                    parsed, errors, total, started_at, workers, cache_hits, 0
                ),
            )
            return

        def read_one(image: Path) -> GameMetadata:
            return read_metadata(
                image,
                timeout=120,
                cancel_event=self.cancel_event,
                use_cache=False,
            )

        def remember_failure(image: Path, detail: str) -> None:
            try:
                self.cache.store_failure(image, detail)
            except Exception:
                pass

        mkpfs_started = time.monotonic()
        if workers == 1:
            for image in misses:
                if self.cancel_event.is_set():
                    break
                try:
                    metadata = read_one(image)
                    parsed.append((image, metadata))
                    try:
                        self.cache.store(image, metadata)
                    except Exception:
                        pass
                except MetadataReadCancelled:
                    break
                except MetadataReadError as exc:
                    detail = str(exc)
                    errors.append((image, detail))
                    remember_failure(image, detail)
                except Exception as exc:
                    detail = f"Unexpected error: {exc}"
                    errors.append((image, detail))
                    remember_failure(image, detail)

                completed += 1
                mkpfs_reads += 1
                self.after(
                    0,
                    lambda done=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                        done, total, started_at, name, workers, cache_hits, reads
                    ),
                )
        else:
            executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ffpfsc-reader")
            future_to_image = {executor.submit(read_one, image): image for image in misses}
            pending = set(future_to_image)
            try:
                while pending and not self.cancel_event.is_set():
                    done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                    for future in done:
                        image = future_to_image[future]
                        try:
                            metadata = future.result()
                            parsed.append((image, metadata))
                            try:
                                self.cache.store(image, metadata)
                            except Exception:
                                pass
                        except MetadataReadCancelled:
                            self.cancel_event.set()
                            break
                        except MetadataReadError as exc:
                            detail = str(exc)
                            errors.append((image, detail))
                            remember_failure(image, detail)
                        except Exception as exc:
                            detail = f"Unexpected error: {exc}"
                            errors.append((image, detail))
                            remember_failure(image, detail)

                        completed += 1
                        mkpfs_reads += 1
                        self.after(
                            0,
                            lambda done_count=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                                done_count, total, started_at, name, workers, cache_hits, reads
                            ),
                        )
            finally:
                if self.cancel_event.is_set():
                    for future in pending:
                        future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

        mkpfs_seconds = time.monotonic() - mkpfs_started
        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(completed, total))
            return

        set_profile(mkpfs_seconds)
        self.after(
            0,
            lambda: self._scan_complete(
                parsed, errors, total, started_at, workers, cache_hits, mkpfs_reads
            ),
        )

    def _scan_complete(
        self,
        parsed: list[tuple[Path, GameMetadata]],
        errors: list[tuple[Path, str]],
        total: int,
        started_at: float,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        super()._scan_complete(
            parsed,
            errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )
        additions: list[str] = []
        if getattr(self, "_last_failure_cache_hits", 0):
            additions.append(
                f"{self._last_failure_cache_hits} unchanged previous error(s) were reused without launching MkPFS."
            )
        if getattr(self, "_last_collapsed_root_count", 0):
            additions.append(
                f"{self._last_collapsed_root_count} nested scan root(s) were skipped because a parent root already covered them."
            )
        if getattr(self, "_last_unavailable_roots", ()):
            additions.append(
                f"{len(self._last_unavailable_roots)} unavailable library root(s) were skipped without removing them from settings."
            )
        profile = getattr(self, "_last_scan_profile", None)
        if profile is not None:
            additions.append(f"Performance: {profile.compact_summary()}.")
            try:
                self._log(
                    "PERF",
                    f"Scan performance • {profile.compact_summary()} • cache hit {profile.cache_hit_ratio:.0%} • "
                    f"{profile.files_per_second:.1f} file(s)/s",
                )
            except Exception:
                pass
        if additions:
            self.progress_note_var.set(self.progress_note_var.get() + " " + " ".join(additions))
