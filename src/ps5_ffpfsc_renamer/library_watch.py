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


def changed_paths(before: LibrarySnapshot, after: LibrarySnapshot) -> tuple[str, ...]:
    old = {path: (size, mtime) for path, size, mtime in before.files}
    new = {path: (size, mtime) for path, size, mtime in after.files}
    changed = set(old).symmetric_difference(new)
    changed.update(path for path in old.keys() & new.keys() if old[path] != new[path])
    return tuple(sorted(changed, key=str.casefold))
