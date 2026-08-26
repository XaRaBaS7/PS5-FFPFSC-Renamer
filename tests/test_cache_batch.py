from pathlib import Path

from ps5_ffpfsc_renamer.cache import MetadataCache
from ps5_ffpfsc_renamer.cache_batch import lookup_cache_batch
from ps5_ffpfsc_renamer.metadata import GameMetadata


def test_batch_cache_resolves_verified_and_failure_rows_together(tmp_path: Path) -> None:
    verified_image = tmp_path / "verified.ffpfsc"
    failed_image = tmp_path / "failed.ffpfsc"
    new_image = tmp_path / "new.ffpfsc"
    verified_image.write_bytes(b"verified")
    failed_image.write_bytes(b"failed")
    new_image.write_bytes(b"new")

    cache = MetadataCache(tmp_path / "cache.sqlite3")
    metadata = GameMetadata("PPSA01285", title_name="Returnal")
    cache.store(verified_image, metadata)
    cache.store_failure(failed_image, "truncated read at offset 0")

    batch = lookup_cache_batch(cache, [verified_image, failed_image, new_image])

    verified = batch.verified[verified_image.resolve()]
    failed = batch.failures[failed_image.resolve()]
    new_verified = batch.verified[new_image.resolve()]
    new_failed = batch.failures[new_image.resolve()]

    assert verified.hit is True
    assert verified.metadata == metadata
    assert verified.source == "path+stat"
    assert batch.failures[verified_image.resolve()].hit is False

    assert batch.verified[failed_image.resolve()].hit is False
    assert failed.hit is True
    assert "truncated" in (failed.error or "")

    assert new_verified.hit is False
    assert new_failed.hit is False


def test_batch_cache_deduplicates_duplicate_paths(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"content")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    cache.store(image, GameMetadata("PPSA00001"))

    batch = lookup_cache_batch(cache, [image, image.resolve(), image])

    assert list(batch.verified) == [image.resolve()]
    assert list(batch.failures) == [image.resolve()]


def test_batch_cache_promotes_renamed_verified_file_before_failure_lookup(tmp_path: Path) -> None:
    original = tmp_path / "old.ffpfsc"
    original.write_bytes((b"0123456789" * 30000) + b"END")
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    metadata = GameMetadata("PPSA01285", title_name="Returnal")
    cache.store(original, metadata)

    renamed = tmp_path / "renamed.ffpfsc"
    original.rename(renamed)

    batch = lookup_cache_batch(cache, [renamed])
    result = batch.verified[renamed.resolve()]

    assert result.hit is True
    assert result.source == "quick-fingerprint"
    assert result.metadata == metadata
    assert batch.failures[renamed.resolve()].hit is False
    # Promotion is durable, so the normal exact lookup is hot afterwards.
    assert cache.lookup(renamed).source == "path+stat"
