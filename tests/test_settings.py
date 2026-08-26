from __future__ import annotations

import json
import os
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


def test_library_root_normalization_does_not_resolve_filesystem(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    root = tmp_path / "offline" / ".." / "Archive"

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("library root settings must not resolve filesystem paths")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    save_library_roots([root], settings)
    loaded = load_library_roots(settings)
    expected = Path(os.path.normpath(os.path.abspath(str(root))))

    assert loaded == [expected]


def test_invalid_settings_do_not_break_startup(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{ definitely not json", encoding="utf-8")

    assert load_settings(settings) == AppSettings()
    assert load_library_roots(settings) == []


def test_complete_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    root = tmp_path / "library"
    mkpfs = tmp_path / "mkpfs-helper.exe"
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
        filename_separator="__",
        result_filter="DUPLICATES",
        window_geometry="1440x900+10+20",
        mkpfs_path=str(mkpfs),
        sort_column="size",
        sort_descending=True,
        autoscan_on_start=False,
        autoscan_on_browse=False,
        autoscan_on_add_folder=False,
        remember_window_geometry=False,
        show_relative_paths=False,
        auto_prune_cache=True,
        watch_library=True,
        watch_interval_seconds=60,
    )

    save_settings(expected, path)
    loaded = load_settings(path)

    assert loaded.library_roots == (str(root.resolve()),)
    assert loaded.recursive is False
    assert loaded.worker == "4 (SSD / NVMe)"
    assert loaded.component_order == ("title", "version", "title_id")
    assert loaded.filename_separator == "__"
    assert loaded.result_filter == "DUPLICATES"
    assert loaded.window_geometry == "1440x900+10+20"
    assert loaded.mkpfs_path == str(mkpfs.resolve())
    assert loaded.sort_column == "size"
    assert loaded.sort_descending is True
    assert loaded.autoscan_on_start is False
    assert loaded.autoscan_on_browse is False
    assert loaded.autoscan_on_add_folder is False
    assert loaded.remember_window_geometry is False
    assert loaded.show_relative_paths is False
    assert loaded.auto_prune_cache is True
    assert loaded.watch_library is True
    assert loaded.watch_interval_seconds == 60


def test_watch_interval_is_normalized_to_supported_values(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(AppSettings(watch_interval_seconds=47), path)
    loaded = load_settings(path)

    assert loaded.watch_interval_seconds == 60


def test_unsafe_filename_separator_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(AppSettings(filename_separator="/"), path)
    loaded = load_settings(path)
    assert loaded.filename_separator == " - "


def test_updating_roots_preserves_other_preferences(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    mkpfs = tmp_path / "mkpfs.exe"
    save_settings(
        AppSettings(
            worker="2",
            include_title=True,
            mkpfs_path=str(mkpfs),
            sort_column="title",
            sort_descending=True,
            autoscan_on_start=False,
            filename_separator="_",
            watch_library=True,
            watch_interval_seconds=120,
        ),
        path,
    )
    root = tmp_path / "new-root"

    save_library_roots([root], path)
    loaded = load_settings(path)

    assert loaded.worker == "2"
    assert loaded.include_title is True
    assert loaded.library_roots == (str(root.resolve()),)
    assert loaded.mkpfs_path == str(mkpfs.resolve())
    assert loaded.sort_column == "title"
    assert loaded.sort_descending is True
    assert loaded.autoscan_on_start is False
    assert loaded.filename_separator == "_"
    assert loaded.watch_library is True
    assert loaded.watch_interval_seconds == 120


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
    assert loaded.mkpfs_path is None
    assert loaded.sort_column == "file"
    assert loaded.sort_descending is False
    assert loaded.autoscan_on_start is True
    assert loaded.autoscan_on_browse is True
    assert loaded.autoscan_on_add_folder is True
    assert loaded.remember_window_geometry is True
    assert loaded.show_relative_paths is True
    assert loaded.auto_prune_cache is False
    assert loaded.filename_separator == " - "
    assert loaded.watch_library is False
    assert loaded.watch_interval_seconds == 30


def test_settings_file_uses_current_schema(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(AppSettings(), path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 7
