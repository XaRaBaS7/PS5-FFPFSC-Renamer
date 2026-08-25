from __future__ import annotations

import json

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


def test_details_cache_moves_with_renamed_ffpfsc(tmp_path, monkeypatch):
    old_path = tmp_path / "Returnal.ffpfsc"
    old_path.write_bytes(b"same-payload")
    cache_root = tmp_path / "cache"
    calls = 0

    def fake_unpack(image_path, output_dir, selectors, *, timeout, cancel_event):
        nonlocal calls
        calls += 1
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")
        (sce_sys / "icon0.png").write_bytes(b"icon")

    monkeypatch.setattr(game_details, "_run_unpack", fake_unpack)
    first = game_details.load_game_details(old_path, cache_root=cache_root)
    assert first.cache_hit is False
    assert calls == 1

    new_path = tmp_path / "PPSA01285 - Returnal.ffpfsc"
    old_path.rename(new_path)
    assert game_details.migrate_details_cache(old_path, new_path, cache_root) is True

    second = game_details.load_game_details(new_path, cache_root=cache_root)
    assert second.cache_hit is True
    assert second.metadata.title_name == "Returnal"
    assert calls == 1
    stats = game_details.details_cache_stats(cache_root)
    assert stats.entries == 1
    assert stats.valid_entries == 1
    assert stats.stale_entries == 0


def test_details_cache_migration_is_noop_when_not_cached(tmp_path):
    old_path = tmp_path / "old.ffpfsc"
    old_path.write_bytes(b"data")
    new_path = tmp_path / "new.ffpfsc"
    old_path.rename(new_path)

    assert game_details.migrate_details_cache(old_path, new_path, tmp_path / "cache") is False
