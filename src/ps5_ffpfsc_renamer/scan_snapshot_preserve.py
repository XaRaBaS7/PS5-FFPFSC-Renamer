from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .scan_snapshot import ScanSnapshot


def _path_key(value: str | Path) -> str:
    return str(value).casefold()


def carry_forward_preserved_entries(
    previous: ScanSnapshot,
    current: ScanSnapshot,
    preserved_paths: Iterable[str | Path],
) -> ScanSnapshot:
    """Keep the last validated baseline for rows preserved from offline roots.

    UI rows may display OFFLINE, but that is an availability state rather than
    a verified file change. Reusing the previous SnapshotEntry prevents a
    disconnected root from producing false REMOVED/CHANGED events and prevents
    OFFLINE->READY noise when the root reconnects.
    """

    preserved = {_path_key(path) for path in preserved_paths}
    if not preserved:
        return current

    previous_by_path = {_path_key(entry.path): entry for entry in previous.entries}
    current_by_path = {_path_key(entry.path): entry for entry in current.entries}

    for key in preserved:
        previous_entry = previous_by_path.get(key)
        if previous_entry is not None:
            current_by_path[key] = previous_entry

    entries = tuple(sorted(current_by_path.values(), key=lambda entry: entry.path.casefold()))
    return replace(current, entries=entries)
