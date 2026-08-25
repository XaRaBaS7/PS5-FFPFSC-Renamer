from __future__ import annotations

import json
from pathlib import Path

from ps5_ffpfsc_renamer.settings import (
    AppSettings,
    load_library_roots,
    load_settings,
    save_library_roots,
    save_settings,
)


def test_library_roots_round_trip(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    first = tmp_path / "games-a"
    second = tmp_path / "games-b"

    save_library_roots([first, second], settings)
    loaded = load_library_roots(settings)

    assert loaded == [first.resolve(), second.resolve()]


def test_library_roots_are_deduplicated_case_insensitively(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    folder = tmp_path / "Games"

    save_library_roots([folder, folder], settings)
    loaded = load_library_roots(settings)

    assert loaded == [folder.resolve()]


def test_invalid_settings_do_not_break_startup(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{ definitely not json", encoding="utf-8")

    assert load_settings(settings) == AppSettings()
    assert load_library_roots(settings) == []


def test_complete_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    root = tmp_path / "library"
    expected = AppSettings(
        library_roots=(str(root),),
        recursive=False,
        worker="4 (SSD / NVMe)",
        preset="Custom",
        include_title_id=True,
        include_title=True,
        include_version=True,
        version_format="Original (01.000.000)",
        version_prefix=False,
        folder_mode="File only",
        component_order=("title", "version", "title_id"),
        result_filter="DUPLICATES",
        window_geometry="1440x900+10+20",
    )

    save_settings(expected, path)
    loaded = load_settings(path)

    assert loaded.library_roots == (str(root.resolve()),)
    assert loaded.recursive is False
    assert loaded.worker == "4 (SSD / NVMe)"
    assert loaded.component_order == ("title", "version", "title_id")
    assert loaded.result_filter == "DUPLICATES"
    assert loaded.window_geometry == "1440x900+10+20"


def test_updating_roots_preserves_other_preferences(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(AppSettings(worker="2", include_title=True), path)
    root = tmp_path / "new-root"

    save_library_roots([root], path)
    loaded = load_settings(path)

    assert loaded.worker == "2"
    assert loaded.include_title is True
    assert loaded.library_roots == (str(root.resolve()),)


def test_schema_v1_migrates_without_failure(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    root = tmp_path / "old-library"
    path.write_text(
        json.dumps({"schema_version": 1, "library_roots": [str(root)]}),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.library_roots == (str(root.resolve()),)
    assert loaded.recursive is True
    assert loaded.folder_mode == "Smart (recommended)"


def test_settings_file_uses_current_schema(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(AppSettings(), path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 2
    assert "worker" in data
    assert "component_order" in data
