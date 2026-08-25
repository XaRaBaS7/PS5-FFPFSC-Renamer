from __future__ import annotations

from pathlib import Path


def scan_ffpfsc(root: Path, recursive: bool = True) -> list[Path]:
    root = root.expanduser()
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_file():
        if root.suffix.lower() != ".ffpfsc":
            raise ValueError(f"Not an .ffpfsc file: {root}")
        return [root.resolve()]

    pattern = "**/*.ffpfsc" if recursive else "*.ffpfsc"
    files = [path.resolve() for path in root.glob(pattern) if path.is_file()]
    return sorted(files, key=lambda path: str(path).casefold())
