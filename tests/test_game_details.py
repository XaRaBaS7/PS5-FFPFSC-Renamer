from __future__ import annotations

import json
from pathlib import Path

from ps5_ffpfsc_renamer import game_details


PARAM = {
    "titleId": "PPSA01285",
    "contentVersion": "01.000.000",
    "masterVersion": "01.000.000",
    "localizedParameters": {
        "defaultLanguage": "en-US",
        "en-US": {"titleName": "Returnal"},
    },
}


def test_load_game_details_extracts_and_then_uses_cache(tmp_path, monkeypatch):
    image = tmp_path / "PPSA01285.ffpfsc"
    image.write_bytes(b"ffpfsc-test")
    cache_root = tmp_path / "cache"
    calls = []

    def fake_unpack(image_path, output_dir, selectors, *, timeout, cancel_event):
        calls.append(tuple(selectors))
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")
        (sce_sys / "icon0.png").write_bytes(b"fake-png")

    monkeypatch.setattr(game_details, "_run_unpack", fake_unpack)

    first = game_details.load_game_details(image, cache_root=cache_root)
    assert first.cache_hit is False
    assert first.metadata.title_id == "PPSA01285"
    assert first.metadata.title_name == "Returnal"
    assert first.icon_path is not None
    assert first.icon_path.is_file()
    assert calls == [("sce_sys/param.json", "sce_sys/icon0.png")]

    second = game_details.load_game_details(image, cache_root=cache_root)
    assert second.cache_hit is True
    assert second.metadata.title_name == "Returnal"
    assert calls == [("sce_sys/param.json", "sce_sys/icon0.png")]


def test_force_bypasses_details_cache(tmp_path, monkeypatch):
    image = tmp_path / "PPSA01285.ffpfsc"
    image.write_bytes(b"ffpfsc-test")
    cache_root = tmp_path / "cache"
    count = 0

    def fake_unpack(image_path, output_dir, selectors, *, timeout, cancel_event):
        nonlocal count
        count += 1
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")

    monkeypatch.setattr(game_details, "_run_unpack", fake_unpack)

    game_details.load_game_details(image, cache_root=cache_root)
    game_details.load_game_details(image, cache_root=cache_root, force=True)
    assert count == 2


def test_cache_key_changes_when_file_identity_changes(tmp_path):
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"a")
    first = game_details.details_cache_key(image)
    image.write_bytes(b"different-size")
    second = game_details.details_cache_key(image)
    assert first != second
