from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.cache import MetadataCache
from ps5_ffpfsc_renamer.cache_prune_policy import (
    can_auto_prune_cache,
    prune_missing_for_roots,
)
from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.root_health import RootStatus, root_key
from ps5_ffpfsc_renamer.ui.startup_preferences_mixin import StartupPreferencesMixin


def test_auto_prune_requires_all_configured_roots_online() -> None:
    local = Path("G:/PS5")
    archive = Path("Z:/Archive")
    statuses = {
        root_key(local): RootStatus(local, "ONLINE", "available"),
        root_key(archive): RootStatus(archive, "OFFLINE", "unavailable"),
    }

    assert can_auto_prune_cache([local, archive], statuses) is False


def test_auto_prune_rejects_unknown_root_state() -> None:
    root = Path("G:/PS5")

    assert can_auto_prune_cache([root], {}) is False


def test_auto_prune_allows_only_fully_online_configuration() -> None:
    first = Path("G:/PS5")
    second = Path("D:/Archive")
    removed = Path("Z:/Removed")
    statuses = {
        root_key(first): RootStatus(first, "ONLINE", "available"),
        root_key(second): RootStatus(second, "ONLINE", "available"),
        root_key(removed): RootStatus(removed, "OFFLINE", "stale state"),
    }

    assert can_auto_prune_cache([first, second], statuses) is True
    assert can_auto_prune_cache([], statuses) is False


def test_scoped_auto_prune_preserves_historical_root_cache(tmp_path: Path) -> None:
    active_root = tmp_path / "active"
    historical_root = tmp_path / "historical"
    active_root.mkdir()
    historical_root.mkdir()

    active_file = active_root / "missing.ffpfsc"
    historical_file = historical_root / "offline.ffpfsc"
    active_file.write_bytes(b"active")
    historical_file.write_bytes(b"historical")

    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(active_file, GameMetadata("PPSA10001"))
    cache.store_failure(historical_file, "previous parser failure")

    active_file.unlink()
    historical_file.unlink()

    removed = prune_missing_for_roots(cache, [active_root])

    assert removed == 1
    assert cache.entry_count() == 0
    assert cache.failure_count() == 1


def test_scoped_auto_prune_does_not_match_similar_prefix_root(tmp_path: Path) -> None:
    active_root = tmp_path / "PS5"
    unrelated_root = tmp_path / "PS5-backup"
    active_root.mkdir()
    unrelated_root.mkdir()

    unrelated = unrelated_root / "old.ffpfsc"
    unrelated.write_bytes(b"old")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(unrelated, GameMetadata("PPSA10002"))
    unrelated.unlink()

    removed = prune_missing_for_roots(cache, [active_root])

    assert removed == 0
    assert cache.entry_count() == 1


class _AutoPruneHarness(StartupPreferencesMixin):
    def __init__(self, root: Path) -> None:
        self.library_roots = [root]
        self._auto_prune_started = False
        self._auto_prune_cache = True
        self._auto_prune_probe_pending = False
        self._scan_active = False
        self._startup_scan_pending = False
        self.root_status = None
        self.probe_callback = None
        self.start_count = 0

    def _root_status(self, _root: Path):
        return self.root_status

    def _probe_library_roots_async(self, *, callback=None) -> None:
        self.probe_callback = callback

    def _start_auto_prune_cache(self) -> None:
        self.start_count += 1

    def after(self, _delay: int, callback) -> None:
        callback()


def test_auto_prune_rechecks_current_roots_after_async_probe(tmp_path: Path) -> None:
    root = tmp_path / "Library"
    harness = _AutoPruneHarness(root)

    harness._schedule_auto_prune_cache()

    assert harness._auto_prune_probe_pending is True
    assert harness.start_count == 0
    assert harness.probe_callback is not None

    harness.root_status = RootStatus(root, "ONLINE", "available")
    harness.probe_callback()

    assert harness._auto_prune_probe_pending is False
    assert harness.start_count == 1
