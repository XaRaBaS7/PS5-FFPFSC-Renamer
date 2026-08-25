from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .scanner import scan_ffpfsc


@dataclass(frozen=True, slots=True)
class LibrarySnapshot:
    files: tuple[tuple[str, int, int], ...]
    unavailable_roots: tuple[str, ...] = ()

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True, slots=True)
class LibraryChanges:
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted((*self.added, *self.removed, *self.modified), key=str.casefold))


def snapshot_library(roots: Iterable[Path], *, recursive: bool = True) -> LibrarySnapshot:
    rows: list[tuple[str, int, int]] = []
    unavailable: list[str] = []
    seen: set[str] = set()

    for raw_root in roots:
        root = Path(raw_root)
        try:
            if not root.exists() or not root.is_dir():
                unavailable.append(str(root))
                continue
            images = scan_ffpfsc(root, recursive=recursive)
        except OSError:
            unavailable.append(str(root))
            continue

        for image in images:
            try:
                resolved = image.resolve(strict=False)
                key = str(resolved).casefold()
                if key in seen:
                    continue
                stat = resolved.stat()
            except OSError:
                continue
            seen.add(key)
            rows.append((str(resolved), int(stat.st_size), int(stat.st_mtime_ns)))

    rows.sort(key=lambda item: item[0].casefold())
    unavailable.sort(key=str.casefold)
    return LibrarySnapshot(tuple(rows), tuple(unavailable))


def diff_snapshots(before: LibrarySnapshot, after: LibrarySnapshot) -> LibraryChanges:
    old = {path: (size, mtime) for path, size, mtime in before.files}
    new = {path: (size, mtime) for path, size, mtime in after.files}
    old_paths = set(old)
    new_paths = set(new)
    added = tuple(sorted(new_paths - old_paths, key=str.casefold))
    removed = tuple(sorted(old_paths - new_paths, key=str.casefold))
    modified = tuple(
        sorted(
            (path for path in old_paths & new_paths if old[path] != new[path]),
            key=str.casefold,
        )
    )
    return LibraryChanges(added=added, removed=removed, modified=modified)


def changed_paths(before: LibrarySnapshot, after: LibrarySnapshot) -> tuple[str, ...]:
    """Backward-compatible flattened change list."""
    return diff_snapshots(before, after).paths
