from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def scan_ffpfsc(root: Path, recursive: bool = True) -> list[Path]:
    """Return FFPFSC files under ``root`` using a low-overhead directory walk.

    ``os.scandir`` exposes cached directory-entry type information on Windows,
    avoiding the extra ``stat``/``resolve`` work that ``Path.glob('**/*')`` can
    perform for every entry. Directory symlinks/reparse links are not followed,
    which also prevents accidental traversal loops.
    """
    root = Path(root).expanduser()
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_file():
        if root.suffix.lower() != ".ffpfsc":
            raise ValueError(f"Not an .ffpfsc file: {root}")
        return [root.resolve()]

    root = root.resolve()
    files: list[Path] = []
    stack = [root]

    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            if entry.name.lower().endswith(".ffpfsc"):
                                # entry.path is already absolute because the
                                # scan root is normalized once above.
                                files.append(Path(entry.path))
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except OSError as exc:
                        raise OSError(
                            f"Unable to inspect directory entry '{entry.path}': {exc}"
                        ) from exc
        except OSError as exc:
            raise OSError(f"Unable to scan folder '{directory}': {exc}") from exc

    return sorted(files, key=lambda path: str(path).casefold())


def collapse_nested_roots(roots: Iterable[Path]) -> list[Path]:
    """Remove roots already covered by another recursive scan root.

    This function is intentionally filesystem-agnostic: callers should pass
    only roots they already know are accessible. Keeping the original selected
    library roots elsewhere preserves UI labels, rename safety and offline-root
    reporting while avoiding duplicate directory traversal.
    """
    normalized: list[Path] = []
    seen: set[str] = set()
    for value in roots:
        root = Path(value).expanduser().resolve(strict=False)
        key = str(root).casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(root)

    normalized.sort(key=lambda path: (len(path.parts), str(path).casefold()))
    effective: list[Path] = []
    for root in normalized:
        covered = False
        for parent in effective:
            try:
                root.relative_to(parent)
            except ValueError:
                continue
            covered = True
            break
        if not covered:
            effective.append(root)
    return effective
