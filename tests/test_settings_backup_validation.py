from __future__ import annotations

import json
from pathlib import Path

import pytest

from ps5_ffpfsc_renamer.settings import AppSettings, SETTINGS_SCHEMA_VERSION
from ps5_ffpfsc_renamer.settings_backup import (
    SettingsBackupError,
    export_settings_backup,
    load_settings_backup,
)


def _export_payload(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    destination = tmp_path / "settings-backup.json"
    export_settings_backup(
        AppSettings(
            library_roots=(str(tmp_path / "library"),),
            worker="2",
            result_filter="CHANGED",
            watch_library=False,
            watch_interval_seconds=30,
        ),
        destination,
    )
    return destination, json.loads(destination.read_text(encoding="utf-8"))


def test_settings_backup_contains_configuration_only(tmp_path: Path) -> None:
    destination, payload = _export_payload(tmp_path)

    assert destination.is_file()
    assert {
        "metadata_cache",
        "details_cache",
        "operation_history",
        "activity_log",
        "ffpfsc",
        "files",
    }.isdisjoint(payload)


def test_settings_backup_rejects_non_configuration_fields(tmp_path: Path) -> None:
    destination, payload = _export_payload(tmp_path)
    payload["operation_history"] = [{"source": "example.ffpfsc"}]
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SettingsBackupError, match="unsupported field"):
        load_settings_backup(destination)


def test_settings_backup_rejects_newer_settings_schema(tmp_path: Path) -> None:
    destination, payload = _export_payload(tmp_path)
    payload["schema_version"] = SETTINGS_SCHEMA_VERSION + 1
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SettingsBackupError, match="newer application schema"):
        load_settings_backup(destination)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("recursive", "yes"),
        ("library_roots", "D:/Games"),
        ("component_order", ["title_id", "title_id"]),
        ("watch_interval_seconds", 17),
        ("filename_separator", "/"),
    ),
)
def test_settings_backup_rejects_invalid_configuration_values(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    destination, payload = _export_payload(tmp_path)
    payload[field] = value
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SettingsBackupError):
        load_settings_backup(destination)
