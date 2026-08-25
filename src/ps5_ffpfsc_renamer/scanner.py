from __future__ import annotations

import os
from pathlib import Path


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
                                files.append(Path(entry.path))
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except OSError as exc:
                        raise OSError(f"Unable to inspect directory entry '{entry.path}': {exc}") from exc
        except OSError as exc:
            raise OSError(f"Unable to scan folder '{directory}': {exc}") from exc

    return sorted(files, key=lambda path: str(path).casefold())
