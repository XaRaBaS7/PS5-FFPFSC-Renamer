from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

from .cache_batch import FileState
from .library_view import ResultRow
from .settings import default_settings_path

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    path: str
    size: int | None
    mtime_ns: int | None
    title_id: str
    title: str
    version: str
    status: str
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class ScanSnapshot:
    created_at: int
    roots: tuple[str, ...]
    entries: tuple[SnapshotEntry, ...]


@dataclass(frozen=True, slots=True)
class SnapshotChange:
    before: SnapshotEntry
    after: SnapshotEntry
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScanDiff:
    previous_created_at: int
    current_created_at: int
    roots_changed: bool
    added: tuple[SnapshotEntry, ...]
    removed: tuple[SnapshotEntry, ...]
    changed: tuple[SnapshotChange, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.roots_changed or self.added or self.removed or self.changed)


def default_scan_snapshot_path() -> Path:
    return default_settings_path().with_name("library-snapshot.json")


def _path_key(value: str | Path) -> str:
    return str(value).casefold()


def _root_set(values: Iterable[str]) -> set[str]:
    return {_path_key(value) for value in values}


def build_scan_snapshot(
    rows: Iterable[ResultRow],
    *,
    roots: Iterable[str | Path],
    file_states: Mapping[Path, FileState] | None = None,
    created_at: int | None = None,
) -> ScanSnapshot:
    states_by_key = {
        _path_key(path): state for path, state in (file_states or {}).items()
    }
    entries: list[SnapshotEntry] = []
    for row in rows:
        path_text = str(row.source)
        state = states_by_key.get(_path_key(path_text))
        size = state.size if state is not None else row.size
        mtime_ns = state.mtime_ns if state is not None else None
        entries.append(
            SnapshotEntry(
                path=path_text,
                size=size,
                mtime_ns=mtime_ns,
                title_id=row.title_id,
                title=row.title,
                version=row.version,
                status=row.status,
                duplicate=bool(row.duplicate),
            )
        )
    entries.sort(key=lambda item: item.path.casefold())
    return ScanSnapshot(
        created_at=int(time.time()) if created_at is None else int(created_at),
        roots=tuple(str(root) for root in roots),
        entries=tuple(entries),
    )


def compare_scan_snapshots(previous: ScanSnapshot, current: ScanSnapshot) -> ScanDiff:
    before_by_path = {_path_key(entry.path): entry for entry in previous.entries}
    after_by_path = {_path_key(entry.path): entry for entry in current.entries}

    added = tuple(
        after_by_path[key]
        for key in sorted(after_by_path.keys() - before_by_path.keys())
    )
    removed = tuple(
        before_by_path[key]
        for key in sorted(before_by_path.keys() - after_by_path.keys())
    )

    changed: list[SnapshotChange] = []
    labels = (
        ("size", "size"),
        ("mtime_ns", "modified time"),
        ("title_id", "Title ID"),
        ("title", "title"),
        ("version", "version"),
        ("status", "status"),
        ("duplicate", "duplicate state"),
    )
    for key in sorted(before_by_path.keys() & after_by_path.keys()):
        before = before_by_path[key]
        after = after_by_path[key]
        fields = tuple(
            label
            for attribute, label in labels
            if getattr(before, attribute) != getattr(after, attribute)
        )
        if fields:
            changed.append(SnapshotChange(before=before, after=after, fields=fields))

    return ScanDiff(
        previous_created_at=previous.created_at,
        current_created_at=current.created_at,
        roots_changed=_root_set(previous.roots) != _root_set(current.roots),
        added=added,
        removed=removed,
        changed=tuple(changed),
    )


def migrate_snapshot_paths(
    snapshot: ScanSnapshot,
    completed: Iterable[tuple[Path, Path]],
) -> ScanSnapshot:
    mapping = {_path_key(old): str(new) for old, new in completed}
    if not mapping:
        return snapshot
    migrated = tuple(
        replace(entry, path=mapping.get(_path_key(entry.path), entry.path))
        for entry in snapshot.entries
    )
    return replace(
        snapshot,
        entries=tuple(sorted(migrated, key=lambda item: item.path.casefold())),
    )


def _entry_to_json(entry: SnapshotEntry) -> dict[str, object]:
    return {
        "path": entry.path,
        "size": entry.size,
        "mtime_ns": entry.mtime_ns,
        "title_id": entry.title_id,
        "title": entry.title,
        "version": entry.version,
        "status": entry.status,
        "duplicate": entry.duplicate,
    }


def save_scan_snapshot(
    snapshot: ScanSnapshot,
    snapshot_path: Path | None = None,
) -> Path:
    path = snapshot_path or default_scan_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_at": snapshot.created_at,
        "roots": list(snapshot.roots),
        "entries": [_entry_to_json(entry) for entry in snapshot.entries],
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_scan_snapshot(snapshot_path: Path | None = None) -> ScanSnapshot | None:
    path = snapshot_path or default_scan_snapshot_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return None

    created_at = payload.get("created_at")
    roots = payload.get("roots")
    raw_entries = payload.get("entries")
    if not isinstance(created_at, int) or not isinstance(roots, list) or not isinstance(raw_entries, list):
        return None

    clean_roots = tuple(value for value in roots if isinstance(value, str) and value.strip())
    entries: list[SnapshotEntry] = []
    for value in raw_entries:
        if not isinstance(value, dict):
            continue
        path_value = value.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        size = value.get("size")
        mtime_ns = value.get("mtime_ns")
        entries.append(
            SnapshotEntry(
                path=path_value,
                size=size if isinstance(size, int) else None,
                mtime_ns=mtime_ns if isinstance(mtime_ns, int) else None,
                title_id=value.get("title_id") if isinstance(value.get("title_id"), str) else "-",
                title=value.get("title") if isinstance(value.get("title"), str) else "-",
                version=value.get("version") if isinstance(value.get("version"), str) else "-",
                status=value.get("status") if isinstance(value.get("status"), str) else "UNKNOWN",
                duplicate=value.get("duplicate") if isinstance(value.get("duplicate"), bool) else False,
            )
        )
    entries.sort(key=lambda item: item.path.casefold())
    return ScanSnapshot(created_at=created_at, roots=clean_roots, entries=tuple(entries))
