from pathlib import Path
import json
import pytest

from ps5_ffpfsc_renamer.settings import AppSettings
from ps5_ffpfsc_renamer.settings_backup import (
    BACKUP_FORMAT,
    BACKUP_FORMAT_VERSION,
    SettingsBackupError,
    export_settings_backup,
    load_settings_backup,
)


def test_settings_backup_round_trip(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    destination = tmp_path / "backup.json"
    settings = AppSettings(
        library_roots=(str(library),),
        recursive=False,
        worker="4 (SSD / NVMe)",
        include_title=True,
        include_version=True,
        filename_separator="_",
        result_filter="PROBLEMS",
        watch_library=True,
        watch_interval_seconds=60,
    )

    export_settings_backup(settings, destination)
    restored = load_settings_backup(destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["backup_format"] == BACKUP_FORMAT
    assert payload["backup_format_version"] == BACKUP_FORMAT_VERSION
    assert restored.library_roots == (str(library.resolve()),)
    assert restored.recursive is False
    assert restored.worker == "4 (SSD / NVMe)"
    assert restored.include_title is True
    assert restored.include_version is True
    assert restored.filename_separator == "_"
    assert restored.result_filter == "PROBLEMS"
    assert restored.watch_library is True
    assert restored.watch_interval_seconds == 60


def test_settings_backup_requires_project_marker(tmp_path: Path) -> None:
    source = tmp_path / "other.json"
    source.write_text(json.dumps({"schema_version": 7}), encoding="utf-8")
    with pytest.raises(SettingsBackupError):
        load_settings_backup(source)


def test_settings_backup_requires_supported_format(tmp_path: Path) -> None:
    source = tmp_path / "future.json"
    source.write_text(
        json.dumps(
            {
                "backup_format": BACKUP_FORMAT,
                "backup_format_version": BACKUP_FORMAT_VERSION + 1,
                "schema_version": 7,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SettingsBackupError):
        load_settings_backup(source)
