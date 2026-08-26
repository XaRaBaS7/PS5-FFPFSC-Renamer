from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Mapping

from .library_view import ResultRow, duplicate_title_ids
from .root_health import RootStatus, root_key
from .scan_snapshot import ScanSnapshot
from .workspace_models import LibraryRecord


def _lexical_absolute(path: Path) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))


def _lexical_key(path: Path) -> str:
    return os.path.normcase(_lexical_absolute(path)).casefold()


def _is_under(path: Path, root: Path) -> bool:
    candidate = _lexical_key(path)
    parent = _lexical_key(root)
    try:
        return os.path.commonpath((candidate, parent)) == parent
    except ValueError:
        return False


def _matching_root(path: Path, roots: Iterable[Path]) -> Path | None:
    matches = [Path(root) for root in roots if _is_under(path, Path(root))]
    if not matches:
        return None
    return max(matches, key=lambda root: len(Path(_lexical_absolute(root)).parts))


def records_from_scan_snapshot(snapshot: ScanSnapshot | None) -> list[LibraryRecord]:
    """Convert a persisted successful-scan baseline to display-only row models."""

    if snapshot is None:
        return []
    return [
        LibraryRecord(
            ResultRow(
                source=Path(entry.path),
                title_id=entry.title_id,
                title=entry.title,
                version=entry.version,
                size=entry.size,
                output="-",
                status=entry.status,
                duplicate=entry.duplicate,
                change="",
            )
        )
        for entry in snapshot.entries
    ]


def merge_preserved_offline_records(
    current_records: Iterable[LibraryRecord],
    previous_records: Iterable[LibraryRecord],
    *,
    roots: Iterable[Path],
    statuses: Mapping[str, RootStatus],
) -> tuple[list[LibraryRecord], tuple[Path, ...]]:
    """Append read-only previous rows for configured roots that are unavailable.

    The function is lexical and performs no filesystem access. Current scan
    results always win. Previous rows are carried forward only when their
    deepest currently configured root is explicitly OFFLINE/ERROR.
    """

    configured_roots = tuple(Path(root) for root in roots)
    current = list(current_records)
    previous = list(previous_records)
    current_keys = {_lexical_key(record.view.source) for record in current}

    preserved: list[LibraryRecord] = []
    preserved_paths: list[Path] = []
    for record in previous:
        source = Path(record.view.source)
        key = _lexical_key(source)
        if key in current_keys:
            continue
        root = _matching_root(source, configured_roots)
        if root is None:
            continue
        status = statuses.get(root_key(root))
        if status is None or status.available:
            continue

        view = replace(
            record.view,
            output="-",
            status="OFFLINE",
            duplicate=False,
            change="",
        )
        preserved.append(
            LibraryRecord(
                view=view,
                plan_item=None,
                detail=record.detail,
                friendly=(
                    "Preserved from the previous successful scan because its configured "
                    "library root is currently unavailable."
                ),
                inference_source=record.inference_source,
            )
        )
        preserved_paths.append(source)
        current_keys.add(key)

    combined = [
        LibraryRecord(
            view=record.view,
            plan_item=record.plan_item,
            detail=record.detail,
            friendly=record.friendly,
            inference_source=record.inference_source,
        )
        for record in current
    ]
    combined.extend(preserved)

    duplicate_ids = duplicate_title_ids([record.view for record in combined])
    for record in combined:
        title_id = record.view.title_id.strip().upper()
        record.view = replace(
            record.view,
            duplicate=bool(title_id and title_id != "-" and title_id in duplicate_ids),
        )

    return combined, tuple(preserved_paths)
