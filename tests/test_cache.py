from pathlib import Path

from ps5_ffpfsc_renamer.cache import MetadataCache, quick_fingerprint
from ps5_ffpfsc_renamer.metadata import GameMetadata


def test_cache_hits_unchanged_path_without_reparse(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"A" * 1024)
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    metadata = GameMetadata(
        "PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )

    cache.store(image, metadata)
    result = cache.lookup(image)

    assert result.hit is True
    assert result.source == "path+stat"
    assert result.metadata == metadata


def test_cache_miss_when_same_path_changes(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"A" * 1024)
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(image, GameMetadata("PPSA01285"))

    image.write_bytes(b"B" * 2048)
    result = cache.lookup(image)

    assert result.hit is False
    assert result.metadata is None


def test_quick_fingerprint_recognizes_renamed_file(tmp_path: Path) -> None:
    original = tmp_path / "old-name.ffpfsc"
    original.write_bytes((b"0123456789" * 30000) + b"END")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    metadata = GameMetadata(
        "PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )
    cache.store(original, metadata)

    renamed = tmp_path / "new-name.ffpfsc"
    original.rename(renamed)

    result = cache.lookup(renamed)
    assert result.hit is True
    assert result.source == "quick-fingerprint"
    assert result.metadata == metadata


def test_quick_fingerprint_changes_when_sampled_content_changes(tmp_path: Path) -> None:
    a = tmp_path / "a.ffpfsc"
    b = tmp_path / "b.ffpfsc"
    a.write_bytes(b"A" * 300000)
    b.write_bytes(b"B" * 300000)

    assert quick_fingerprint(a) != quick_fingerprint(b)


def test_cache_clear(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    failed = tmp_path / "failed.ffpfsc"
    image.write_bytes(b"data")
    failed.write_bytes(b"broken")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(image, GameMetadata("PPSA01285"))
    cache.store_failure(failed, "no inner exFAT found")
    assert cache.entry_count() == 1
    assert cache.failure_count() == 1

    cache.clear()
    assert cache.entry_count() == 0
    assert cache.failure_count() == 0


def test_cache_stats_report_entries_and_database_size(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    failed = tmp_path / "failed.ffpfsc"
    image.write_bytes(b"data")
    failed.write_bytes(b"broken")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(image, GameMetadata("PPSA01285"))
    cache.store_failure(failed, "parser failed")

    stats = cache.stats()

    assert stats.entries == 1
    assert stats.failed_entries == 1
    assert stats.database_bytes > 0
    assert stats.oldest_updated_at is not None
    assert stats.newest_updated_at is not None


def test_prune_missing_removes_only_stale_paths(tmp_path: Path) -> None:
    keep = tmp_path / "keep.ffpfsc"
    stale = tmp_path / "stale.ffpfsc"
    failed = tmp_path / "failed.ffpfsc"
    keep.write_bytes(b"keep")
    stale.write_bytes(b"stale")
    failed.write_bytes(b"failed")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(keep, GameMetadata("PPSA00001"))
    cache.store(stale, GameMetadata("PPSA00002"))
    cache.store_failure(failed, "bad image")
    stale.unlink()
    failed.unlink()

    removed = cache.prune_missing()

    assert removed == 2
    assert cache.entry_count() == 1
    assert cache.failure_count() == 0
    assert cache.lookup(keep).hit is True


def test_failure_cache_hits_only_when_file_stat_is_unchanged(tmp_path: Path) -> None:
    image = tmp_path / "broken.ffpfsc"
    image.write_bytes(b"broken")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store_failure(image, "truncated read at offset 0")

    hit = cache.lookup_failure(image)
    assert hit.hit is True
    assert "truncated" in (hit.error or "")

    image.write_bytes(b"changed-and-longer")
    miss = cache.lookup_failure(image)
    assert miss.hit is False


def test_verified_store_replaces_failure_cache_entry(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"content")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store_failure(image, "temporary parser failure")
    assert cache.failure_count() == 1

    cache.store(image, GameMetadata("PPSA12345"))

    assert cache.failure_count() == 0
    assert cache.lookup(image).hit is True


def test_batch_lookup_returns_multiple_exact_hits(tmp_path: Path) -> None:
    first = tmp_path / "first.ffpfsc"
    second = tmp_path / "second.ffpfsc"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(first, GameMetadata("PPSA00001"))
    cache.store(second, GameMetadata("PPSA00002"))

    results = cache.lookup_many([first, second])

    assert results[first.resolve()].hit is True
    assert results[second.resolve()].hit is True
    assert results[first.resolve()].source == "path+stat"
    assert results[second.resolve()].source == "path+stat"
