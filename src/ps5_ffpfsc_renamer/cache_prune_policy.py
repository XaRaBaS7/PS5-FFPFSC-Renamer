from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping

from .cache import MetadataCache
from .root_health import RootStatus, root_key


def can_auto_prune_cache(
    roots: Iterable[Path],
    statuses: Mapping[str, RootStatus],
) -> bool:
    """Return true only when every configured root is confirmed online."""

    configured = tuple(Path(root) for root in roots)
    if not configured:
        return False
    for root in configured:
        status = statuses.get(root_key(root))
        if status is None or not status.available:
            return False
    return True


def _scope_path(value: Path) -> str:
    """Normalize a path lexically without probing the filesystem."""

    return os.path.normcase(os.path.abspath(os.path.expanduser(str(value))))


def _is_under_roots(path: Path, roots: tuple[str, ...]) -> bool:
    candidate = _scope_path(path)
    for root in roots:
        try:
            if os.path.commonpath((candidate, root)) == root:
                return True
        except ValueError:
            # Different Windows drives, or otherwise incomparable paths.
            continue
    return False


def prune_missing_for_roots(cache: MetadataCache, roots: Iterable[Path]) -> int:
    """Prune stale cache rows only inside the supplied active library roots.

    Paths outside the current root set are deliberately left untouched and are
    not probed with ``exists()``. This keeps automatic startup maintenance from
    waking or invalidating cache data for disconnected historical USB/NAS roots.
    Manual Cache Manager pruning can still use ``MetadataCache.prune_missing``
    when a global cleanup is explicitly requested.
    """

    scoped_roots = tuple(dict.fromkeys(_scope_path(Path(root)) for root in roots))
    if not scoped_roots:
        return 0

    removed = 0
    with cache._connect() as connection:
        for table in ("metadata_cache", "failure_cache"):
            rows = connection.execute(f"SELECT path_key, path FROM {table}").fetchall()
            missing: list[str] = []
            for row in rows:
                path = Path(row["path"])
                if not _is_under_roots(path, scoped_roots):
                    continue
                if not path.exists():
                    missing.append(str(row["path_key"]))
            if missing:
                connection.executemany(
                    f"DELETE FROM {table} WHERE path_key = ?",
                    [(key,) for key in missing],
                )
                removed += len(missing)
    return removed
