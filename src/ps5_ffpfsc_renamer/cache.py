from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .metadata import GameMetadata

CACHE_SCHEMA_VERSION = 1
FAILURE_SCHEMA_VERSION = 1
FINGERPRINT_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class CacheLookup:
    metadata: GameMetadata | None
    hit: bool
    source: str = "miss"


@dataclass(frozen=True, slots=True)
class FailureLookup:
    error: str | None
    hit: bool
    updated_at: int | None = None


@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
    failed_entries: int
    database_bytes: int
    oldest_updated_at: int | None
    newest_updated_at: int | None


def default_cache_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / "PS5-FFPFSC-Renamer"
    else:
        root = Path.home() / ".ps5-ffpfsc-renamer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "metadata-cache.sqlite3"


def _path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def quick_fingerprint(path: Path) -> str:
    """Fingerprint a huge file without reading it all.

    The digest includes file size plus small samples from the start, middle and
    end. It is intended only as a fast cache identity hint, not as a security
    or archival checksum.
    """
    stat = path.stat()
    size = stat.st_size
    digest = hashlib.blake2b(digest_size=20)
    digest.update(str(size).encode("ascii"))

    if size == 0:
        return digest.hexdigest()

    offsets = [0]
    if size > FINGERPRINT_CHUNK_SIZE * 2:
        middle = max(0, (size // 2) - (FINGERPRINT_CHUNK_SIZE // 2))
        offsets.append(middle)
    if size > FINGERPRINT_CHUNK_SIZE:
        offsets.append(max(0, size - FINGERPRINT_CHUNK_SIZE))

    with path.open("rb", buffering=0) as handle:
        seen: set[int] = set()
        for offset in offsets:
            if offset in seen:
                continue
            seen.add(offset)
            handle.seek(offset)
            digest.update(handle.read(FINGERPRINT_CHUNK_SIZE))

    return digest.hexdigest()


class MetadataCache:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = (db_path or default_cache_path()).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    path_key TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    fingerprint TEXT,
                    title_id TEXT NOT NULL,
                    title_name TEXT,
                    content_version TEXT,
                    master_version TEXT,
                    schema_version INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metadata_cache_size
                ON metadata_cache(size, schema_version)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metadata_cache_fingerprint
                ON metadata_cache(size, fingerprint, schema_version)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS failure_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    path_key TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    error TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_failure_cache_stat
                ON failure_cache(size, mtime_ns, schema_version)
                """
            )

    @staticmethod
    def _metadata_from_row(row: sqlite3.Row) -> GameMetadata:
        return GameMetadata(
            title_id=row["title_id"],
            title_name=row["title_name"],
            content_version=row["content_version"],
            master_version=row["master_version"],
        )

    def lookup(self, path: Path) -> CacheLookup:
        return self.lookup_many([path]).get(path.resolve(), CacheLookup(None, False))

    def lookup_many(self, paths: Iterable[Path]) -> dict[Path, CacheLookup]:
        """Resolve verified metadata cache hits with a single SQLite read.

        Exact path+size+mtime hits require no file reads. Only path-changed files
        whose size matches an existing cached image pay the lightweight sampled
        fingerprint cost.
        """
        resolved: list[Path] = []
        stats: dict[Path, os.stat_result] = {}
        results: dict[Path, CacheLookup] = {}
        seen: set[str] = set()
        for value in paths:
            path = Path(value).resolve()
            key = _path_key(path)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(path)
            try:
                stats[path] = path.stat()
            except OSError:
                results[path] = CacheLookup(None, False)

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM metadata_cache WHERE schema_version = ?",
                (CACHE_SCHEMA_VERSION,),
            ).fetchall()

        by_key = {row["path_key"]: row for row in rows}
        by_size: dict[int, list[sqlite3.Row]] = {}
        for row in rows:
            if row["fingerprint"]:
                by_size.setdefault(int(row["size"]), []).append(row)

        fingerprint_promotions: list[tuple[Path, GameMetadata, str]] = []
        for path in resolved:
            stat = stats.get(path)
            if stat is None:
                continue
            row = by_key.get(_path_key(path))
            if (
                row is not None
                and int(row["size"]) == stat.st_size
                and int(row["mtime_ns"]) == stat.st_mtime_ns
            ):
                results[path] = CacheLookup(self._metadata_from_row(row), True, "path+stat")
                continue

            candidates = by_size.get(stat.st_size, [])
            if not candidates:
                results[path] = CacheLookup(None, False)
                continue
            try:
                fingerprint = quick_fingerprint(path)
            except OSError:
                results[path] = CacheLookup(None, False)
                continue
            matched = next(
                (candidate for candidate in candidates if candidate["fingerprint"] == fingerprint),
                None,
            )
            if matched is None:
                results[path] = CacheLookup(None, False)
                continue
            metadata = self._metadata_from_row(matched)
            results[path] = CacheLookup(metadata, True, "quick-fingerprint")
            fingerprint_promotions.append((path, metadata, fingerprint))

        for path, metadata, fingerprint in fingerprint_promotions:
            try:
                self.store(path, metadata, fingerprint=fingerprint)
            except OSError:
                pass
        return results

    def lookup_failure(self, path: Path) -> FailureLookup:
        return self.lookup_failures_many([path]).get(path.resolve(), FailureLookup(None, False))

    def lookup_failures_many(self, paths: Iterable[Path]) -> dict[Path, FailureLookup]:
        """Return cached MkPFS failures only when the exact file stat is unchanged."""
        resolved: list[Path] = []
        stats: dict[Path, os.stat_result] = {}
        results: dict[Path, FailureLookup] = {}
        seen: set[str] = set()
        for value in paths:
            path = Path(value).resolve()
            key = _path_key(path)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(path)
            try:
                stats[path] = path.stat()
            except OSError:
                results[path] = FailureLookup(None, False)

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM failure_cache WHERE schema_version = ?",
                (FAILURE_SCHEMA_VERSION,),
            ).fetchall()
        by_key = {row["path_key"]: row for row in rows}

        for path in resolved:
            stat = stats.get(path)
            if stat is None:
                continue
            row = by_key.get(_path_key(path))
            if (
                row is not None
                and int(row["size"]) == stat.st_size
                and int(row["mtime_ns"]) == stat.st_mtime_ns
            ):
                results[path] = FailureLookup(
                    str(row["error"]),
                    True,
                    int(row["updated_at"]),
                )
            else:
                results[path] = FailureLookup(None, False)
        return results

    def store(
        self,
        path: Path,
        metadata: GameMetadata,
        *,
        fingerprint: str | None = None,
    ) -> None:
        path = path.resolve()
        stat = path.stat()
        if fingerprint is None:
            try:
                fingerprint = quick_fingerprint(path)
            except OSError:
                fingerprint = None

        now = int(time.time())
        key = _path_key(path)
        with self._connect() as connection:
            connection.execute("DELETE FROM failure_cache WHERE path_key = ?", (key,))
            connection.execute(
                """
                INSERT INTO metadata_cache (
                    path, path_key, size, mtime_ns, fingerprint,
                    title_id, title_name, content_version, master_version,
                    schema_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path_key) DO UPDATE SET
                    path = excluded.path,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    fingerprint = excluded.fingerprint,
                    title_id = excluded.title_id,
                    title_name = excluded.title_name,
                    content_version = excluded.content_version,
                    master_version = excluded.master_version,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at
                """,
                (
                    str(path),
                    key,
                    stat.st_size,
                    stat.st_mtime_ns,
                    fingerprint,
                    metadata.title_id,
                    metadata.title_name,
                    metadata.content_version,
                    metadata.master_version,
                    CACHE_SCHEMA_VERSION,
                    now,
                ),
            )

    def store_failure(self, path: Path, error: str) -> None:
        path = path.resolve()
        stat = path.stat()
        key = _path_key(path)
        now = int(time.time())
        detail = str(error).strip() or "Unknown MkPFS metadata read error"
        with self._connect() as connection:
            connection.execute("DELETE FROM metadata_cache WHERE path_key = ?", (key,))
            connection.execute(
                """
                INSERT INTO failure_cache (
                    path, path_key, size, mtime_ns, error, schema_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path_key) DO UPDATE SET
                    path = excluded.path,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    error = excluded.error,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at
                """,
                (
                    str(path),
                    key,
                    stat.st_size,
                    stat.st_mtime_ns,
                    detail,
                    FAILURE_SCHEMA_VERSION,
                    now,
                ),
            )

    def update_path_after_rename(self, old_path: Path, new_path: Path) -> None:
        """Keep verified or failure cache records hot after an app rename."""
        old_key = _path_key(old_path)
        new_path = new_path.resolve()
        if not new_path.exists():
            return
        stat = new_path.stat()
        new_key = _path_key(new_path)
        now = int(time.time())

        with self._connect() as connection:
            for table in ("metadata_cache", "failure_cache"):
                row = connection.execute(
                    f"SELECT path_key FROM {table} WHERE path_key = ?",
                    (old_key,),
                ).fetchone()
                if row is None:
                    continue
                connection.execute(f"DELETE FROM {table} WHERE path_key = ?", (new_key,))
                connection.execute(
                    f"""
                    UPDATE {table}
                    SET path = ?, path_key = ?, size = ?, mtime_ns = ?, updated_at = ?
                    WHERE path_key = ?
                    """,
                    (str(new_path), new_key, stat.st_size, stat.st_mtime_ns, now, old_key),
                )

    def remove(self, path: Path) -> None:
        """Remove cached verified/failure records after a file moves away."""
        key = _path_key(path)
        with self._connect() as connection:
            connection.execute("DELETE FROM metadata_cache WHERE path_key = ?", (key,))
            connection.execute("DELETE FROM failure_cache WHERE path_key = ?", (key,))

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM metadata_cache")
            connection.execute("DELETE FROM failure_cache")

    def entry_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM metadata_cache WHERE schema_version = ?",
                (CACHE_SCHEMA_VERSION,),
            ).fetchone()
        return int(row["count"] if row is not None else 0)

    def failure_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM failure_cache WHERE schema_version = ?",
                (FAILURE_SCHEMA_VERSION,),
            ).fetchone()
        return int(row["count"] if row is not None else 0)

    def stats(self) -> CacheStats:
        with self._connect() as connection:
            metadata = connection.execute(
                """
                SELECT COUNT(*) AS count, MIN(updated_at) AS oldest, MAX(updated_at) AS newest
                FROM metadata_cache WHERE schema_version = ?
                """,
                (CACHE_SCHEMA_VERSION,),
            ).fetchone()
            failures = connection.execute(
                """
                SELECT COUNT(*) AS count, MIN(updated_at) AS oldest, MAX(updated_at) AS newest
                FROM failure_cache WHERE schema_version = ?
                """,
                (FAILURE_SCHEMA_VERSION,),
            ).fetchone()

        timestamps = [
            value
            for value in (
                metadata["oldest"] if metadata is not None else None,
                metadata["newest"] if metadata is not None else None,
                failures["oldest"] if failures is not None else None,
                failures["newest"] if failures is not None else None,
            )
            if value is not None
        ]
        oldest = min(timestamps) if timestamps else None
        newest = max(timestamps) if timestamps else None

        database_bytes = 0
        for candidate in (
            self.db_path,
            self.db_path.with_name(self.db_path.name + "-wal"),
            self.db_path.with_name(self.db_path.name + "-shm"),
        ):
            try:
                database_bytes += candidate.stat().st_size
            except OSError:
                pass

        return CacheStats(
            entries=int(metadata["count"] if metadata is not None else 0),
            failed_entries=int(failures["count"] if failures is not None else 0),
            database_bytes=database_bytes,
            oldest_updated_at=int(oldest) if oldest is not None else None,
            newest_updated_at=int(newest) if newest is not None else None,
        )

    def prune_missing(self) -> int:
        """Remove verified/failure entries whose recorded path no longer exists."""
        removed = 0
        with self._connect() as connection:
            for table in ("metadata_cache", "failure_cache"):
                rows = connection.execute(f"SELECT path_key, path FROM {table}").fetchall()
                missing = [row["path_key"] for row in rows if not Path(row["path"]).exists()]
                if missing:
                    connection.executemany(
                        f"DELETE FROM {table} WHERE path_key = ?",
                        [(key,) for key in missing],
                    )
                    removed += len(missing)
        return removed

    def vacuum(self) -> None:
        """Compact the SQLite file after large cache cleanup operations."""
        connection = self._connect()
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        finally:
            connection.close()
