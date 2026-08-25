from __future__ import annotations

import json
from pathlib import Path

from ps5_ffpfsc_renamer.settings import load_library_roots, save_library_roots


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

    assert load_library_roots(settings) == []


def test_settings_file_contains_only_persistent_library_roots(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    folder = tmp_path / "library"

    save_library_roots([folder], settings)
    data = json.loads(settings.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["library_roots"] == [str(folder.resolve())]
