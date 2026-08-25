from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .metadata import GameMetadata

CACHE_SCHEMA_VERSION = 1
FINGERPRINT_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class CacheLookup:
    metadata: GameMetadata | None
    hit: bool
    source: str = "miss"


@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
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
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
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

    @staticmethod
    def _metadata_from_row(row: sqlite3.Row) -> GameMetadata:
        return GameMetadata(
            title_id=row["title_id"],
            title_name=row["title_name"],
            content_version=row["content_version"],
            master_version=row["master_version"],
        )

    def lookup(self, path: Path) -> CacheLookup:
        path = path.resolve()
        try:
            stat = path.stat()
        except OSError:
            return CacheLookup(None, False)

        key = _path_key(path)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM metadata_cache
                WHERE path_key = ? AND schema_version = ?
                """,
                (key, CACHE_SCHEMA_VERSION),
            ).fetchone()

            if (
                row is not None
                and row["size"] == stat.st_size
                and row["mtime_ns"] == stat.st_mtime_ns
            ):
                return CacheLookup(self._metadata_from_row(row), True, "path+stat")

            candidates = connection.execute(
                """
                SELECT * FROM metadata_cache
                WHERE size = ? AND schema_version = ? AND fingerprint IS NOT NULL
                """,
                (stat.st_size, CACHE_SCHEMA_VERSION),
            ).fetchall()

        if not candidates:
            return CacheLookup(None, False)

        try:
            fingerprint = quick_fingerprint(path)
        except OSError:
            return CacheLookup(None, False)

        matched = next((row for row in candidates if row["fingerprint"] == fingerprint), None)
        if matched is None:
            return CacheLookup(None, False)

        metadata = self._metadata_from_row(matched)
        self.store(path, metadata, fingerprint=fingerprint)
        return CacheLookup(metadata, True, "quick-fingerprint")

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

    def update_path_after_rename(self, old_path: Path, new_path: Path) -> None:
        """Keep a cache record hot after a rename performed by this app."""
        old_key = _path_key(old_path)
        new_path = new_path.resolve()
        if not new_path.exists():
            return
        stat = new_path.stat()
        new_key = _path_key(new_path)

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM metadata_cache WHERE path_key = ?",
                (old_key,),
            ).fetchone()
            if row is None:
                return

            connection.execute("DELETE FROM metadata_cache WHERE path_key = ?", (new_key,))
            connection.execute(
                """
                UPDATE metadata_cache
                SET path = ?, path_key = ?, size = ?, mtime_ns = ?, updated_at = ?
                WHERE path_key = ?
                """,
                (
                    str(new_path),
                    new_key,
                    stat.st_size,
                    stat.st_mtime_ns,
                    int(time.time()),
                    old_key,
                ),
            )

    def remove(self, path: Path) -> None:
        """Remove one cached record after the user deletes/moves a file away."""
        key = _path_key(path)
        with self._connect() as connection:
            connection.execute("DELETE FROM metadata_cache WHERE path_key = ?", (key,))

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM metadata_cache")

    def entry_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM metadata_cache WHERE schema_version = ?",
                (CACHE_SCHEMA_VERSION,),
            ).fetchone()
        return int(row["count"] if row is not None else 0)

    def stats(self) -> CacheStats:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count,
                       MIN(updated_at) AS oldest,
                       MAX(updated_at) AS newest
                FROM metadata_cache
                WHERE schema_version = ?
                """,
                (CACHE_SCHEMA_VERSION,),
            ).fetchone()

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
            entries=int(row["count"] if row is not None else 0),
            database_bytes=database_bytes,
            oldest_updated_at=(
                int(row["oldest"])
                if row is not None and row["oldest"] is not None
                else None
            ),
            newest_updated_at=(
                int(row["newest"])
                if row is not None and row["newest"] is not None
                else None
            ),
        )

    def prune_missing(self) -> int:
        """Remove cache entries whose recorded file path no longer exists."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path_key, path FROM metadata_cache WHERE schema_version = ?",
                (CACHE_SCHEMA_VERSION,),
            ).fetchall()
            missing = [row["path_key"] for row in rows if not Path(row["path"]).exists()]
            if missing:
                connection.executemany(
                    "DELETE FROM metadata_cache WHERE path_key = ?",
                    [(key,) for key in missing],
                )
        return len(missing)

    def vacuum(self) -> None:
        """Compact the SQLite file after large cache cleanup operations."""
        connection = self._connect()
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        finally:
            connection.close()
