from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path


BRAND_ASSET_DIR = Path("assets") / "brand"
BRAND_ICON_NAME = "app-symbol.png"
BRAND_LOGO_NAME = "ps5-ffpfsc-renamer-logo.png"


def _runtime_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


def brand_asset_path(name: str) -> Path | None:
    """Return a bundled/development brand asset without probing library roots."""

    path = _runtime_root() / BRAND_ASSET_DIR / name
    try:
        return path if path.is_file() else None
    except OSError:
        return None


def load_brand_photo(
    master: tk.Misc,
    name: str,
    *,
    subsample: int = 1,
) -> tk.PhotoImage | None:
    path = brand_asset_path(name)
    if path is None:
        return None
    try:
        photo = tk.PhotoImage(master=master, file=str(path))
        if subsample > 1:
            photo = photo.subsample(int(subsample), int(subsample))
        return photo
    except (OSError, tk.TclError):
        return None
