from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .ffpfsc_reader import MetadataReadCancelled
from .game_details import load_game_details

ProgressCallback = Callable[[int, int, Path, str], None]


@dataclass(frozen=True, slots=True)
class DetailsPrefetchResult:
    total: int
    cached: int
    loaded: int
    failed: int
    cancelled: bool
    errors: tuple[tuple[str, str], ...] = ()


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in paths:
        path = Path(value).expanduser().resolve(strict=False)
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def prefetch_game_details(
    paths: Iterable[Path],
    *,
    workers: int = 1,
    timeout: int = 120,
    cancel_event: threading.Event | None = None,
    progress: ProgressCallback | None = None,
    loader=load_game_details,
) -> DetailsPrefetchResult:
    """Populate the details cache for a bounded set of FFPFSC paths."""
    images = _dedupe_paths(paths)
    total = len(images)
    if not images:
        return DetailsPrefetchResult(0, 0, 0, 0, False)

    event = cancel_event or threading.Event()
    cached = 0
    loaded = 0
    failed = 0
    completed = 0
    errors: list[tuple[str, str]] = []

    def report(path: Path, state: str) -> None:
        nonlocal completed
        completed += 1
        if progress is not None:
            progress(completed, total, path, state)

    def accept(path: Path, details) -> None:
        nonlocal cached, loaded
        if bool(getattr(details, "cache_hit", False)):
            cached += 1
            report(path, "cache")
        else:
            loaded += 1
            report(path, "loaded")

    def reject(path: Path, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        errors.append((str(path), str(exc)))
        report(path, "error")

    def read_one(path: Path):
        return loader(path, timeout=timeout, cancel_event=event, force=False)

    max_workers = max(1, min(int(workers), 2, total))
    if max_workers == 1:
        for path in images:
            if event.is_set():
                break
            try:
                details = read_one(path)
            except MetadataReadCancelled:
                event.set()
                report(path, "cancelled")
                break
            except Exception as exc:
                reject(path, exc)
            else:
                accept(path, details)
    else:
        executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ffpfsc-details")
        future_to_path = {executor.submit(read_one, path): path for path in images}
        pending = set(future_to_path)
        try:
            while pending and not event.is_set():
                done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    path = future_to_path[future]
                    try:
                        details = future.result()
                    except MetadataReadCancelled:
                        event.set()
                        report(path, "cancelled")
                        break
                    except Exception as exc:
                        reject(path, exc)
                    else:
                        accept(path, details)
        finally:
            if event.is_set():
                for future in pending:
                    future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)

    return DetailsPrefetchResult(
        total=total,
        cached=cached,
        loaded=loaded,
        failed=failed,
        cancelled=event.is_set(),
        errors=tuple(errors),
    )
