from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

SETTINGS_SCHEMA_VERSION = 1


def default_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / "PS5-FFPFSC-Renamer"
    else:
        root = Path.home() / ".ps5-ffpfsc-renamer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


def _dedupe_paths(values: Iterable[str | Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        path = Path(text).expanduser()
        try:
            normalized = path.resolve(strict=False)
        except OSError:
            normalized = path.absolute()
        key = str(normalized).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def load_library_roots(settings_path: Path | None = None) -> list[Path]:
    """Load persisted scan roots. Invalid settings never prevent app startup."""
    path = settings_path or default_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, dict):
        return []
    roots = data.get("library_roots", [])
    if not isinstance(roots, list):
        return []
    return _dedupe_paths(value for value in roots if isinstance(value, str))


def save_library_roots(
    roots: Iterable[str | Path],
    settings_path: Path | None = None,
) -> Path:
    """Persist scan roots atomically so a partial write cannot corrupt settings."""
    path = settings_path or default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _dedupe_paths(roots)
    payload = {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "library_roots": [str(root) for root in normalized],
    }

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
