from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

SETTINGS_SCHEMA_VERSION = 6


@dataclass(frozen=True, slots=True)
class AppSettings:
    library_roots: tuple[str, ...] = ()
    recursive: bool = True
    worker: str = "1 (HDD / safest)"
    preset: str = "PPSA only (compatible)"
    include_title_id: bool = True
    include_title: bool = False
    include_version: bool = False
    version_format: str = "Compact (1.0 / 2.5)"
    version_prefix: bool = True
    folder_mode: str = "Smart (recommended)"
    component_order: tuple[str, ...] = ("title_id", "title", "version")
    result_filter: str = "ALL"
    window_geometry: str | None = None
    mkpfs_path: str | None = None
    sort_column: str = "file"
    sort_descending: bool = False

    # Desktop behavior.
    autoscan_on_start: bool = True
    autoscan_on_browse: bool = True
    autoscan_on_add_folder: bool = True
    remember_window_geometry: bool = True
    show_relative_paths: bool = True
    auto_prune_cache: bool = False

    # v0.4 Smart Library behavior. Disabled by default so HDDs/network shares
    # are never polled unless the user explicitly opts in.
    watch_library: bool = False
    watch_interval_seconds: int = 30


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


def _atomic_write(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _safe_component_order(value: object) -> tuple[str, ...]:
    allowed = ("title_id", "title", "version")
    if not isinstance(value, list):
        return allowed
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item in allowed and item not in result:
            result.append(item)
    for item in allowed:
        if item not in result:
            result.append(item)
    return tuple(result)


def _safe_optional_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return str(Path(text).expanduser().resolve(strict=False))
    except OSError:
        return str(Path(text).expanduser().absolute())


def _bool_setting(data: dict[str, object], key: str, default: bool) -> bool:
    value = data.get(key)
    return value if isinstance(value, bool) else default


def _watch_interval(value: object, default: int = 30) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    allowed = (15, 30, 60, 120)
    return min(allowed, key=lambda item: abs(item - parsed))


def load_settings(settings_path: Path | None = None) -> AppSettings:
    """Load settings defensively, including migration from older schemas."""
    path = settings_path or default_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()

    roots_raw = data.get("library_roots", [])
    roots = (
        tuple(
            str(path)
            for path in _dedupe_paths(
                value for value in roots_raw if isinstance(value, str)
            )
        )
        if isinstance(roots_raw, list)
        else ()
    )

    defaults = AppSettings()
    return AppSettings(
        library_roots=roots,
        recursive=_bool_setting(data, "recursive", defaults.recursive),
        worker=data.get("worker") if isinstance(data.get("worker"), str) else defaults.worker,
        preset=data.get("preset") if isinstance(data.get("preset"), str) else defaults.preset,
        include_title_id=_bool_setting(data, "include_title_id", defaults.include_title_id),
        include_title=_bool_setting(data, "include_title", defaults.include_title),
        include_version=_bool_setting(data, "include_version", defaults.include_version),
        version_format=(
            data.get("version_format")
            if isinstance(data.get("version_format"), str)
            else defaults.version_format
        ),
        version_prefix=_bool_setting(data, "version_prefix", defaults.version_prefix),
        folder_mode=data.get("folder_mode") if isinstance(data.get("folder_mode"), str) else defaults.folder_mode,
        component_order=_safe_component_order(data.get("component_order")),
        result_filter=(
            data.get("result_filter")
            if isinstance(data.get("result_filter"), str)
            else defaults.result_filter
        ),
        window_geometry=(
            data.get("window_geometry")
            if isinstance(data.get("window_geometry"), str)
            else None
        ),
        mkpfs_path=_safe_optional_path(data.get("mkpfs_path")),
        sort_column=(
            data.get("sort_column")
            if isinstance(data.get("sort_column"), str)
            else defaults.sort_column
        ),
        sort_descending=_bool_setting(data, "sort_descending", defaults.sort_descending),
        autoscan_on_start=_bool_setting(data, "autoscan_on_start", defaults.autoscan_on_start),
        autoscan_on_browse=_bool_setting(data, "autoscan_on_browse", defaults.autoscan_on_browse),
        autoscan_on_add_folder=_bool_setting(
            data, "autoscan_on_add_folder", defaults.autoscan_on_add_folder
        ),
        remember_window_geometry=_bool_setting(
            data, "remember_window_geometry", defaults.remember_window_geometry
        ),
        show_relative_paths=_bool_setting(data, "show_relative_paths", defaults.show_relative_paths),
        auto_prune_cache=_bool_setting(data, "auto_prune_cache", defaults.auto_prune_cache),
        watch_library=_bool_setting(data, "watch_library", defaults.watch_library),
        watch_interval_seconds=_watch_interval(
            data.get("watch_interval_seconds"), defaults.watch_interval_seconds
        ),
    )


def save_settings(settings: AppSettings, settings_path: Path | None = None) -> Path:
    path = settings_path or default_settings_path()
    normalized_roots = tuple(str(item) for item in _dedupe_paths(settings.library_roots))
    normalized = replace(
        settings,
        library_roots=normalized_roots,
        mkpfs_path=_safe_optional_path(settings.mkpfs_path),
        watch_interval_seconds=_watch_interval(settings.watch_interval_seconds),
    )
    payload = asdict(normalized)
    payload["schema_version"] = SETTINGS_SCHEMA_VERSION
    payload["library_roots"] = list(normalized.library_roots)
    payload["component_order"] = list(normalized.component_order)
    return _atomic_write(path, payload)


def load_library_roots(settings_path: Path | None = None) -> list[Path]:
    """Backward-compatible helper used by the v0.1.8 GUI layer."""
    return [Path(value) for value in load_settings(settings_path).library_roots]


def save_library_roots(
    roots: Iterable[str | Path],
    settings_path: Path | None = None,
) -> Path:
    """Update only library roots without discarding the other preferences."""
    path = settings_path or default_settings_path()
    current = load_settings(path)
    normalized = tuple(str(item) for item in _dedupe_paths(roots))
    return save_settings(replace(current, library_roots=normalized), path)
