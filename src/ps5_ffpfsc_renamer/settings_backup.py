from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

from .settings import (
    AppSettings,
    SETTINGS_SCHEMA_VERSION,
    load_settings,
    save_settings,
)

BACKUP_FORMAT = "PS5-FFPFSC-Renamer-settings"
BACKUP_FORMAT_VERSION = 1

_BACKUP_METADATA_KEYS = {
    "backup_format",
    "backup_format_version",
    "schema_version",
}
_SETTING_KEYS = {field.name for field in fields(AppSettings)}
_ALLOWED_KEYS = _BACKUP_METADATA_KEYS | _SETTING_KEYS

_BOOL_FIELDS = {
    "recursive",
    "include_title_id",
    "include_title",
    "include_version",
    "version_prefix",
    "sort_descending",
    "autoscan_on_start",
    "autoscan_on_browse",
    "autoscan_on_add_folder",
    "remember_window_geometry",
    "show_relative_paths",
    "auto_prune_cache",
    "watch_library",
}
_STRING_FIELDS = {
    "worker",
    "preset",
    "version_format",
    "folder_mode",
    "filename_separator",
    "result_filter",
    "sort_column",
}
_OPTIONAL_STRING_FIELDS = {"window_geometry", "mkpfs_path"}
_SEQUENCE_FIELDS = {"library_roots", "component_order"}
_COMPONENTS = {"title_id", "title", "version"}
_WATCH_INTERVALS = {15, 30, 60, 120}
_INVALID_SEPARATOR_CHARS = set('<>:"/\\|?*\x00')


class SettingsBackupError(ValueError):
    """Raised when a settings backup is unreadable or unsafe to restore."""


def _validate_string_sequence(payload: dict[str, object], key: str) -> None:
    if key not in payload:
        return
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SettingsBackupError(f"Settings backup field '{key}' must be a list of strings.")


def _validate_backup_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise SettingsBackupError("Settings backup root must be a JSON object.")

    if payload.get("backup_format") != BACKUP_FORMAT:
        raise SettingsBackupError(
            "The selected JSON file is not a PS5 FFPFSC Renamer settings backup."
        )

    format_version = payload.get("backup_format_version")
    if type(format_version) is not int or format_version != BACKUP_FORMAT_VERSION:
        raise SettingsBackupError("Unsupported settings backup format version.")

    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version < 1:
        raise SettingsBackupError("Settings backup is missing a valid schema version.")
    if schema_version > SETTINGS_SCHEMA_VERSION:
        raise SettingsBackupError(
            "Settings backup was created by a newer application schema and cannot be restored safely."
        )

    unknown = sorted(set(payload) - _ALLOWED_KEYS)
    if unknown:
        raise SettingsBackupError(
            "Settings backup contains unsupported field(s): " + ", ".join(unknown)
        )

    for key in _BOOL_FIELDS:
        if key in payload and type(payload[key]) is not bool:
            raise SettingsBackupError(f"Settings backup field '{key}' must be true or false.")

    for key in _STRING_FIELDS:
        if key in payload and not isinstance(payload[key], str):
            raise SettingsBackupError(f"Settings backup field '{key}' must be a string.")

    for key in _OPTIONAL_STRING_FIELDS:
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            raise SettingsBackupError(
                f"Settings backup field '{key}' must be a string or null."
            )

    for key in _SEQUENCE_FIELDS:
        _validate_string_sequence(payload, key)

    roots = payload.get("library_roots")
    if isinstance(roots, list) and any("\x00" in item for item in roots):
        raise SettingsBackupError("Settings backup contains an invalid library path.")

    component_order = payload.get("component_order")
    if isinstance(component_order, list):
        if any(item not in _COMPONENTS for item in component_order):
            raise SettingsBackupError("Settings backup contains an unknown filename component.")
        if len(component_order) != len(set(component_order)):
            raise SettingsBackupError("Settings backup contains duplicate filename components.")

    separator = payload.get("filename_separator")
    if isinstance(separator, str):
        if len(separator) > 12 or any(char in _INVALID_SEPARATOR_CHARS for char in separator):
            raise SettingsBackupError("Settings backup contains an invalid filename separator.")

    if "watch_interval_seconds" in payload:
        interval = payload["watch_interval_seconds"]
        if type(interval) is not int or interval not in _WATCH_INTERVALS:
            raise SettingsBackupError(
                "Settings backup contains an unsupported Live Watch interval."
            )

    return payload


def export_settings_backup(settings: AppSettings, destination: Path) -> Path:
    """Write a portable configuration-only settings backup."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    stage = destination.with_name(f".{destination.name}.{uuid4().hex}.settings-stage")
    try:
        save_settings(settings, stage)
        payload = json.loads(stage.read_text(encoding="utf-8"))
    finally:
        try:
            stage.unlink()
        except OSError:
            pass

    payload["backup_format"] = BACKUP_FORMAT
    payload["backup_format_version"] = BACKUP_FORMAT_VERSION
    _validate_backup_payload(payload)

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_settings_backup(source: Path) -> AppSettings:
    """Validate a settings backup before parsing it through the canonical loader."""
    source = Path(source)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsBackupError(f"Unable to read settings backup: {exc}") from exc

    _validate_backup_payload(payload)
    return load_settings(source)
