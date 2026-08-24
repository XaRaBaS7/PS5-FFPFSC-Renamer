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
    image.write_bytes(b"data")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(image, GameMetadata("PPSA01285"))
    assert cache.entry_count() == 1

    cache.clear()
    assert cache.entry_count() == 0
