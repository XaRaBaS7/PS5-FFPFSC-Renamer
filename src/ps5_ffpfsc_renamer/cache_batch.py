from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .cache import (
    CACHE_SCHEMA_VERSION,
    FAILURE_SCHEMA_VERSION,
    CacheLookup,
    FailureLookup,
    MetadataCache,
    quick_fingerprint,
)
from .metadata import GameMetadata


@dataclass(frozen=True, slots=True)
class FileState:
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class BatchCacheLookup:
    """Verified/failure cache results plus the stat already read for each file."""

    verified: dict[Path, CacheLookup]
    failures: dict[Path, FailureLookup]
    file_states: dict[Path, FileState]


def _normalized(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _key(path: Path) -> str:
    return str(path).casefold()


def lookup_cache_batch(cache: MetadataCache, paths: Iterable[Path]) -> BatchCacheLookup:
    """Resolve both cache layers with one stat per unique source path.

    Lookup priority is intentionally identical to the established behavior:
    exact verified metadata -> moved-file fingerprint promotion -> exact
    unchanged failure-cache hit -> miss. The captured stat is returned so
    downstream features (scan diff, health, telemetry) do not need to touch the
    same huge files again.
    """
    ordered: list[Path] = []
    stats = {}
    file_states: dict[Path, FileState] = {}
    verified: dict[Path, CacheLookup] = {}
    failures: dict[Path, FailureLookup] = {}
    seen: set[str] = set()

    for value in paths:
        path = _normalized(Path(value))
        key = _key(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
        try:
            stat = path.stat()
            stats[path] = stat
            file_states[path] = FileState(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
        except OSError:
            verified[path] = CacheLookup(None, False)
            failures[path] = FailureLookup(None, False)

    with cache._connect() as connection:  # package-internal fast path
        metadata_rows = connection.execute(
            "SELECT * FROM metadata_cache WHERE schema_version = ?",
            (CACHE_SCHEMA_VERSION,),
        ).fetchall()
        failure_rows = connection.execute(
            "SELECT * FROM failure_cache WHERE schema_version = ?",
            (FAILURE_SCHEMA_VERSION,),
        ).fetchall()

    metadata_by_key = {str(row["path_key"]): row for row in metadata_rows}
    failure_by_key = {str(row["path_key"]): row for row in failure_rows}
    metadata_by_size: dict[int, list] = {}
    for row in metadata_rows:
        if row["fingerprint"]:
            metadata_by_size.setdefault(int(row["size"]), []).append(row)

    promotions: list[tuple[Path, GameMetadata, str]] = []
    for path in ordered:
        stat = stats.get(path)
        if stat is None:
            continue
        key = _key(path)
        metadata_row = metadata_by_key.get(key)
        if (
            metadata_row is not None
            and int(metadata_row["size"]) == stat.st_size
            and int(metadata_row["mtime_ns"]) == stat.st_mtime_ns
        ):
            verified[path] = CacheLookup(
                cache._metadata_from_row(metadata_row),
                True,
                "path+stat",
            )
            failures[path] = FailureLookup(None, False)
            continue

        candidates = metadata_by_size.get(stat.st_size, ())
        if candidates:
            try:
                fingerprint = quick_fingerprint(path)
            except OSError:
                fingerprint = None
            if fingerprint is not None:
                matched = next(
                    (row for row in candidates if row["fingerprint"] == fingerprint),
                    None,
                )
                if matched is not None:
                    metadata = cache._metadata_from_row(matched)
                    verified[path] = CacheLookup(metadata, True, "quick-fingerprint")
                    failures[path] = FailureLookup(None, False)
                    promotions.append((path, metadata, fingerprint))
                    continue

        verified[path] = CacheLookup(None, False)
        failure_row = failure_by_key.get(key)
        if (
            failure_row is not None
            and int(failure_row["size"]) == stat.st_size
            and int(failure_row["mtime_ns"]) == stat.st_mtime_ns
        ):
            failures[path] = FailureLookup(
                str(failure_row["error"]),
                True,
                int(failure_row["updated_at"]),
            )
        else:
            failures[path] = FailureLookup(None, False)

    # Promotions are rare and already have a proven durable write path. Keeping
    # that code here makes the common exact-hit path cheap without duplicating
    # cache mutation logic.
    for path, metadata, fingerprint in promotions:
        try:
            cache.store(path, metadata, fingerprint=fingerprint)
        except OSError:
            pass

    return BatchCacheLookup(
        verified=verified,
        failures=failures,
        file_states=file_states,
    )
