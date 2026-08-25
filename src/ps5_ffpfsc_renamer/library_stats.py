from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .library_view import ResultRow


@dataclass(frozen=True, slots=True)
class LibraryStats:
    total_files: int
    total_size: int
    known_size_files: int
    unique_title_ids: int
    duplicate_groups: int
    duplicate_files: int
    status_counts: tuple[tuple[str, int], ...]
    largest: tuple[ResultRow, ...]

    @property
    def average_size(self) -> int | None:
        if self.known_size_files <= 0:
            return None
        return self.total_size // self.known_size_files


def summarize_library(rows: Iterable[ResultRow], *, largest_limit: int = 10) -> LibraryStats:
    items = list(rows)
    status_counter = Counter((row.status or "UNKNOWN").upper() for row in items)

    title_counts: Counter[str] = Counter()
    for row in items:
        title_id = row.title_id.strip().upper()
        if title_id and title_id != "-":
            title_counts[title_id] += 1

    duplicate_ids = {title_id for title_id, count in title_counts.items() if count > 1}
    duplicate_files = sum(title_counts[title_id] for title_id in duplicate_ids)

    sized = [row for row in items if row.size is not None and row.size >= 0]
    total_size = sum(int(row.size or 0) for row in sized)
    largest = tuple(
        sorted(
            sized,
            key=lambda row: int(row.size or 0),
            reverse=True,
        )[: max(0, largest_limit)]
    )

    preferred_order = (
        "READY",
        "UNCHANGED",
        "PARTIAL",
        "COLLISION",
        "INVALID",
        "ERROR",
    )
    ordered_statuses: list[tuple[str, int]] = []
    seen: set[str] = set()
    for status in preferred_order:
        if status in status_counter:
            ordered_statuses.append((status, status_counter[status]))
            seen.add(status)
    for status in sorted(status_counter):
        if status not in seen:
            ordered_statuses.append((status, status_counter[status]))

    return LibraryStats(
        total_files=len(items),
        total_size=total_size,
        known_size_files=len(sized),
        unique_title_ids=len(title_counts),
        duplicate_groups=len(duplicate_ids),
        duplicate_files=duplicate_files,
        status_counts=tuple(ordered_statuses),
        largest=largest,
    )
