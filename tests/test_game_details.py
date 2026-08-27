from __future__ import annotations

import json
from pathlib import Path

import pytest

from ps5_ffpfsc_renamer import game_details
from ps5_ffpfsc_renamer.ffpfsc_reader import MetadataReadError
from ps5_ffpfsc_renamer.process_utils import DEFAULT_MKPFS_MEMORY_LIMIT_BYTES


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


def test_packaged_details_use_bounded_helper_without_stock_fallback(tmp_path, monkeypatch):
    image = tmp_path / "PPSA01285.ffpfsc"
    image.write_bytes(b"ffpfsc-test")
    helper = tmp_path / "mkpfs-helper.exe"
    helper.write_bytes(b"helper")
    cache_root = tmp_path / "cache"
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(game_details, "get_mkpfs_executable", lambda: None)
    monkeypatch.setattr(game_details, "_bundled_mkpfs_helper", lambda: helper)

    def bounded(helper_path, image_path, output_dir, *, timeout, cancel_event):
        calls.append((helper_path.name, image_path.name))
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")
        (sce_sys / "icon0.png").write_bytes(b"bounded-icon")

    def forbidden_unpack(*_args, **_kwargs):
        raise AssertionError("packaged details must not use normal recursive MkPFS unpack")

    monkeypatch.setattr(game_details, "_run_bundled_details", bounded)
    monkeypatch.setattr(game_details, "_run_unpack", forbidden_unpack)

    details = game_details.load_game_details(image, cache_root=cache_root)

    assert calls == [("mkpfs-helper.exe", "PPSA01285.ffpfsc")]
    assert details.metadata.title_id == "PPSA01285"
    assert details.icon_path is not None
    assert details.icon_path.read_bytes() == b"bounded-icon"


def test_bundled_details_stop_at_memory_safety_limit(tmp_path, monkeypatch):
    image = tmp_path / "large.ffpfsc"
    image.write_bytes(b"image")
    helper = tmp_path / "mkpfs-helper.exe"
    helper.write_bytes(b"helper")
    output_dir = tmp_path / "extract"

    class FakeProcess:
        pid = 4242
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            if self.returncode is None:
                self.returncode = 0
            return self.returncode

        def kill(self):
            self.returncode = -9

    process = FakeProcess()
    monkeypatch.setattr(game_details.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        game_details,
        "process_working_set_bytes",
        lambda _process: DEFAULT_MKPFS_MEMORY_LIMIT_BYTES + 1,
    )

    with pytest.raises(MetadataReadError, match="memory safety limit exceeded"):
        game_details._run_bundled_details(
            helper,
            image,
            output_dir,
            timeout=120,
            cancel_event=None,
        )

    assert process.returncode == -15


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


def test_details_cache_stats_and_prune_stale_entries(tmp_path, monkeypatch):
    image = tmp_path / "PPSA01285.ffpfsc"
    image.write_bytes(b"ffpfsc-test")
    cache_root = tmp_path / "cache"

    def fake_unpack(image_path, output_dir, selectors, *, timeout, cancel_event):
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")
        (sce_sys / "icon0.png").write_bytes(b"fake-png-data")

    monkeypatch.setattr(game_details, "_run_unpack", fake_unpack)
    game_details.load_game_details(image, cache_root=cache_root)

    before = game_details.details_cache_stats(cache_root)
    assert before.entries == 1
    assert before.valid_entries == 1
    assert before.stale_entries == 0
    assert before.bytes_on_disk > 0

    image.write_bytes(b"changed-identity-and-size")
    stale = game_details.details_cache_stats(cache_root)
    assert stale.entries == 1
    assert stale.valid_entries == 0
    assert stale.stale_entries == 1

    assert game_details.prune_details_cache(cache_root) == 1
    after = game_details.details_cache_stats(cache_root)
    assert after.entries == 0
    assert after.bytes_on_disk == 0


def test_clear_details_cache_removes_all_entries(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"

    def fake_unpack(image_path, output_dir, selectors, *, timeout, cancel_event):
        sce_sys = output_dir / "sce_sys"
        sce_sys.mkdir(parents=True, exist_ok=True)
        (sce_sys / "param.json").write_text(json.dumps(PARAM), encoding="utf-8")

    monkeypatch.setattr(game_details, "_run_unpack", fake_unpack)

    for index in range(2):
        image = tmp_path / f"PPSA0128{index}.ffpfsc"
        image.write_bytes(f"ffpfsc-{index}".encode())
        param = dict(PARAM)
        param["titleId"] = f"PPSA0128{index}"

        def per_file_unpack(image_path, output_dir, selectors, *, timeout, cancel_event, data=param):
            sce_sys = output_dir / "sce_sys"
            sce_sys.mkdir(parents=True, exist_ok=True)
            (sce_sys / "param.json").write_text(json.dumps(data), encoding="utf-8")

        monkeypatch.setattr(game_details, "_run_unpack", per_file_unpack)
        game_details.load_game_details(image, cache_root=cache_root)

    assert game_details.details_cache_stats(cache_root).entries == 2
    assert game_details.clear_details_cache(cache_root) == 2
    assert game_details.details_cache_stats(cache_root).entries == 0
