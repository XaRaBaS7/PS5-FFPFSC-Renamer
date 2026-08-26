from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .library_view import ResultRow
from .root_health import RootStatus, root_key

RESULT_FILTERS = (
    "ALL",
    "READY",
    "UNCHANGED",
    "PARTIAL",
    "COLLISION",
    "INVALID",
    "ERROR",
    "OFFLINE",
    "HEALTHY",
    "PROBLEMS",
    "ADDED",
    "CHANGED",
    "DUPLICATES",
)

PROBLEM_STATUSES = frozenset({"PARTIAL", "COLLISION", "INVALID", "ERROR"})


@dataclass(frozen=True, slots=True)
class LibraryStatusSummary:
    """Compact in-memory summary for the desktop library status line."""

    visible_count: int
    selected_count: int
    root_count: int
    online_root_count: int
    offline_count: int
    problem_count: int
    duplicate_group_count: int
    added_count: int
    changed_count: int

    def text(self) -> str:
        problem_label = "problem" if self.problem_count == 1 else "problems"
        duplicate_label = (
            "duplicate group" if self.duplicate_group_count == 1 else "duplicate groups"
        )
        parts = [
            f"{self.visible_count} visible",
            f"{self.selected_count} selected",
        ]
        if self.root_count:
            parts.append(f"roots {self.online_root_count}/{self.root_count} online")
        else:
            parts.append("roots 0")
        if self.offline_count:
            parts.append(f"{self.offline_count} offline")
        parts.append(f"{self.problem_count} {problem_label}")
        parts.append(f"{self.duplicate_group_count} {duplicate_label}")
        if self.added_count or self.changed_count:
            parts.append(f"changes +{self.added_count} / ~{self.changed_count}")
        return " • ".join(parts)


def configured_root_statuses(
    roots: Iterable[Path],
    statuses: Mapping[str, RootStatus],
) -> tuple[RootStatus, ...]:
    """Return known states for configured roots, excluding stale status entries."""

    current: list[RootStatus] = []
    for root in roots:
        status = statuses.get(root_key(root))
        if status is not None:
            current.append(status)
    return tuple(current)


def summarize_library_status(
    rows: Iterable[ResultRow],
    *,
    visible_count: int,
    selected_count: int,
    root_count: int,
    root_statuses: Iterable[RootStatus],
) -> LibraryStatusSummary:
    """Build a status summary using only already available in-memory state."""

    records = tuple(rows)
    duplicate_ids = {
        row.title_id.strip().upper()
        for row in records
        if row.duplicate and row.title_id.strip() and row.title_id.strip() != "-"
    }
    statuses = tuple(root_statuses)
    return LibraryStatusSummary(
        visible_count=max(0, int(visible_count)),
        selected_count=max(0, int(selected_count)),
        root_count=max(0, int(root_count)),
        online_root_count=sum(1 for status in statuses if status.state == "ONLINE"),
        offline_count=sum(1 for row in records if row.status.upper() == "OFFLINE"),
        problem_count=sum(1 for row in records if row.status.upper() in PROBLEM_STATUSES),
        duplicate_group_count=len(duplicate_ids),
        added_count=sum(1 for row in records if row.change.upper() == "ADDED"),
        changed_count=sum(1 for row in records if row.change.upper() == "CHANGED"),
    )
