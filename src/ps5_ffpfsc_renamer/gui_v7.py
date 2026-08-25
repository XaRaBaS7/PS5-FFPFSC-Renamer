from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .diagnostics import classify_reader_error, infer_metadata_from_path
from .ffpfsc_reader import MetadataReadCancelled, MetadataReadError, read_metadata
from .gui_v5 import RenamerApp as RenamerAppV5
from .gui_v6 import PartialItem, RenamerApp as RenamerAppV6
from .metadata import GameMetadata
from .naming import NamingOptions
from .scanner import scan_ffpfsc


class RenamerApp(RenamerAppV6):
    """GUI with automatic Browse scanning and multi-folder libraries."""

    def __init__(self) -> None:
        self.library_roots: list[Path] = []
        super().__init__()

    # ------------------------------------------------------ library controls
    def _build_library_controls(self, card: ttk.Frame) -> None:
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="FFPFSC library", style="CardTitle.TLabel").pack(side="left")
        self.folder_count_var = tk.StringVar(value="No folders selected")
        ttk.Label(
            header,
            textvariable=self.folder_count_var,
            style="CardMuted.TLabel",
        ).pack(side="right")

        ttk.Label(
            card,
            text="Browse starts scanning automatically. Add more folders to analyze them as one library.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 7))

        path_row = ttk.Frame(card, style="Card.TFrame")
        path_row.pack(fill="x")
        self.folder_entry = tk.Entry(
            path_row,
            textvariable=self.folder_var,
            bg="#211a2f",
            fg="#f4f0ff",
            insertbackground="#f4f0ff",
            selectbackground="#8b5cf6",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#3a304d",
            highlightcolor="#8b5cf6",
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 7))

        self.browse_button = ttk.Button(
            path_row,
            text="Browse",
            style="Secondary.TButton",
            command=self._browse,
        )
        self.browse_button.pack(side="left")
        self.add_folder_button = ttk.Button(
            path_row,
            text="+ Add folder",
            style="Secondary.TButton",
            command=self._add_folder,
        )
        self.add_folder_button.pack(side="left", padx=(6, 0))

        options = ttk.Frame(card, style="Card.TFrame")
        options.pack(fill="x", pady=(8, 0))
        self.recursive_check = ttk.Checkbutton(
            options,
            text="Include subfolders",
            variable=self.recursive_var,
        )
        self.recursive_check.pack(side="left")
        ttk.Label(options, text="Workers", style="CardMuted.TLabel").pack(
            side="left", padx=(14, 5)
        )
        self.worker_combo = ttk.Combobox(
            options,
            textvariable=self.worker_var,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=17,
            style="Performance.TCombobox",
        )
        self.worker_combo.pack(side="left")

        self.manage_folders_button = ttk.Button(
            options,
            text="Folders (0)...",
            style="Secondary.TButton",
            command=self._manage_folders,
        )
        self.manage_folders_button.pack(side="left", padx=(8, 0))

        self.scan_button = ttk.Button(
            options,
            text="Scan library",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.pack(side="right")

    @staticmethod
    def _root_key(path: Path) -> str:
        return str(path.resolve()).casefold()

    def _normalize_roots(self) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for root in self.library_roots:
            try:
                resolved = root.expanduser().resolve()
            except OSError:
                continue
            key = self._root_key(resolved)
            if key in seen:
                continue
            seen.add(key)
            unique.append(resolved)
        self.library_roots = unique

    def _update_root_summary(self) -> None:
        self._normalize_roots()
        count = len(self.library_roots)
        if count:
            self.folder_var.set(str(self.library_roots[0]))
            self.folder_count_var.set(f"{count} folder{'s' if count != 1 else ''} selected")
        else:
            self.folder_var.set("")
            self.folder_count_var.set("No folders selected")
        self.manage_folders_button.configure(text=f"Folders ({count})...")

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select FFPFSC folder")
        if not selected:
            return
        self.library_roots = [Path(selected).resolve()]
        self._update_root_summary()
        # Browse is intentionally one-click: select a folder and immediately scan.
        self.after(30, self._scan)

    def _add_folder(self) -> None:
        selected = filedialog.askdirectory(title="Add folder to FFPFSC scan")
        if not selected:
            return
        candidate = Path(selected).resolve()
        existing = {self._root_key(root) for root in self.library_roots}
        if self._root_key(candidate) not in existing:
            self.library_roots.append(candidate)
        self._update_root_summary()
        # Re-scan the whole logical library. Cached roots return almost instantly,
        # so in practice only files from the newly added folder need MkPFS work.
        self.after(30, self._scan)

    def _manage_folders(self) -> None:
        window = tk.Toplevel(self)
        window.title("Scan folders")
        window.transient(self)
        window.grab_set()
        window.geometry("720x330")
        window.minsize(560, 280)

        container = ttk.Frame(window, padding=14)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Folders included in scan", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            container,
            text="The same file is analyzed only once even when selected roots overlap.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        listbox = tk.Listbox(
            container,
            bg="#181321",
            fg="#f4f0ff",
            selectbackground="#6d4bc3",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#3a304d",
            font=("Segoe UI", 9),
        )
        listbox.pack(fill="both", expand=True)

        def refresh() -> None:
            listbox.delete(0, "end")
            for root in self.library_roots:
                listbox.insert("end", str(root))
            self._update_root_summary()

        def add_here() -> None:
            selected = filedialog.askdirectory(title="Add folder", parent=window)
            if not selected:
                return
            candidate = Path(selected).resolve()
            if self._root_key(candidate) not in {
                self._root_key(root) for root in self.library_roots
            }:
                self.library_roots.append(candidate)
            refresh()

        def remove_selected() -> None:
            indexes = list(listbox.curselection())
            if not indexes:
                return
            for index in reversed(indexes):
                if 0 <= index < len(self.library_roots):
                    del self.library_roots[index]
            refresh()

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="+ Add", command=add_here).pack(side="left")
        ttk.Button(buttons, text="Remove", command=remove_selected).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(
            buttons,
            text="Clear all",
            command=lambda: (self.library_roots.clear(), refresh()),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

        def apply_and_scan() -> None:
            refresh()
            window.destroy()
            if self.library_roots:
                self.after(30, self._scan)

        ttk.Button(
            buttons,
            text="Scan selected folders",
            style="Primary.TButton",
            command=apply_and_scan,
        ).pack(side="right", padx=(0, 6))
        refresh()

    def _set_scan_controls(self, active: bool) -> None:
        super()._set_scan_controls(active)
        state = "disabled" if active else "normal"
        self.add_folder_button.configure(state=state)
        self.manage_folders_button.configure(state=state)

    def _scan(self) -> None:
        if not self.library_roots:
            folder_text = self.folder_var.get().strip()
            if folder_text:
                candidate = Path(folder_text).expanduser()
                if candidate.is_dir():
                    self.library_roots = [candidate.resolve()]
                    self._update_root_summary()
        super()._scan()

    # ------------------------------------------------------ multi-root scan
    def _scan_worker(self, folder: Path, recursive: bool, worker_setting: str) -> None:
        started_at = time.monotonic()
        roots = list(self.library_roots) or [folder]
        try:
            images: list[Path] = []
            seen: set[str] = set()
            for root in roots:
                for image in scan_ffpfsc(root, recursive=recursive):
                    key = str(image.resolve()).casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    images.append(image.resolve())
            images.sort(key=lambda path: str(path).casefold())
        except Exception as exc:
            self.after(0, lambda detail=str(exc): self._scan_failed(detail))
            return

        total = len(images)
        cached_items: list[tuple[Path, GameMetadata]] = []
        misses: list[Path] = []

        self.after(0, lambda: self.files_var.set(str(total)))
        for index, image in enumerate(images, start=1):
            if self.cancel_event.is_set():
                self.after(0, lambda: self._scan_cancelled(len(cached_items), total))
                return
            try:
                lookup = self.cache.lookup(image)
            except Exception:
                lookup = None

            if lookup is not None and lookup.hit and lookup.metadata is not None:
                cached_items.append((image, lookup.metadata))
            else:
                misses.append(image)

            self.after(
                0,
                lambda done=index, hits=len(cached_items), new=len(misses): self._cache_check_progress(
                    done, total, hits, new
                ),
            )

        cache_hits = len(cached_items)
        workers = self._resolve_worker_count(worker_setting, len(misses))
        self.after(0, lambda: self._analysis_started(total, cache_hits, len(misses), workers))

        parsed = list(cached_items)
        errors: list[tuple[Path, str]] = []
        completed = cache_hits
        mkpfs_reads = 0

        if not misses:
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
                    errors.append((image, str(exc)))
                except Exception as exc:
                    errors.append((image, f"Unexpected error: {exc}"))

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
                            errors.append((image, str(exc)))
                        except Exception as exc:
                            errors.append((image, f"Unexpected error: {exc}"))

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

        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(completed, total))
            return

        self.after(
            0,
            lambda: self._scan_complete(
                parsed, errors, total, started_at, workers, cache_hits, mkpfs_reads
            ),
        )

    # ---------------------------------------------------------- root mapping
    def _matching_root(self, path: Path) -> Path | None:
        path = path.resolve()
        matches: list[Path] = []
        for root in self.library_roots:
            try:
                path.relative_to(root.resolve())
            except ValueError:
                continue
            matches.append(root.resolve())
        if not matches:
            return None
        return max(matches, key=lambda item: len(item.parts))

    def _display_source(self, source: Path) -> str:
        root = self._matching_root(source)
        if root is None:
            return source.name
        try:
            relative = source.resolve().relative_to(root)
        except ValueError:
            return source.name
        if len(self.library_roots) <= 1:
            return str(relative)
        return str(Path(root.name) / relative)

    def _current_naming_options(self) -> NamingOptions:
        options = super()._current_naming_options()
        return replace(
            options,
            library_root=str(self.library_roots[0]) if len(self.library_roots) == 1 else None,
            library_roots=tuple(str(root) for root in self.library_roots),
        )

    # ------------------------------------------------------ partial metadata
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
        partial: list[PartialItem] = []
        hard_errors: list[tuple[Path, str]] = []

        for image, detail in errors:
            inferred = infer_metadata_from_path(image, library_root=self._matching_root(image))
            code, friendly = classify_reader_error(detail)
            if inferred is None:
                hard_errors.append((image, detail))
                continue
            partial.append(
                (
                    image,
                    inferred.metadata,
                    detail,
                    inferred.source,
                    code,
                    friendly,
                )
            )

        self.partial_items = partial
        # Bypass gui_v6's single-root inference; its row rendering still runs
        # through dynamic dispatch from the v5 completion method.
        RenamerAppV5._scan_complete(
            self,
            parsed,
            hard_errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )

        partial_count = len(partial)
        hard_count = len(hard_errors)
        if partial_count:
            self.progress_note_var.set(
                f"Scan complete across {len(self.library_roots)} folder(s): {cache_hits} reused from cache, "
                f"{mkpfs_reads} read with MkPFS, {partial_count} shown as PARTIAL."
            )
        else:
            self.progress_note_var.set(
                f"Scan complete across {len(self.library_roots)} folder(s): {cache_hits} reused from cache, "
                f"{mkpfs_reads} read with MkPFS."
            )
        self.status_var.set(
            f"Scan complete — {len(self.library_roots)} folder(s), {cache_hits} cached, "
            f"{mkpfs_reads} new/changed, {partial_count} partial, {hard_count} error(s)"
        )


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
