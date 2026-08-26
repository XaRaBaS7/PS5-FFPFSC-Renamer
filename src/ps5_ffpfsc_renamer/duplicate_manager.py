from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .library_view import ResultRow


@dataclass(frozen=True, slots=True)
class DuplicateGroupSummary:
    """In-memory summary for one duplicated Title ID group."""

    title_id: str
    title: str
    file_count: int
    versions: tuple[str, ...]
    status_counts: tuple[tuple[str, int], ...]
    known_size_files: int
    total_size: int | None
    same_size: bool | None

    @property
    def status_text(self) -> str:
        return ", ".join(f"{status}:{count}" for status, count in self.status_counts)

    @property
    def versions_text(self) -> str:
        return ", ".join(self.versions) if self.versions else "-"

    @property
    def size_state(self) -> str:
        if self.same_size is True:
            return "same size"
        if self.same_size is False:
            return "different sizes"
        return "size incomplete"


def duplicate_row_groups(rows: Iterable[ResultRow]) -> dict[str, tuple[ResultRow, ...]]:
    """Return case-insensitive duplicated Title ID groups without filesystem I/O."""
    grouped: dict[str, list[ResultRow]] = defaultdict(list)
    for row in rows:
        title_id = row.title_id.strip().upper()
        if not title_id or title_id == "-":
            continue
        grouped[title_id].append(row)
    return {
        title_id: tuple(group)
        for title_id, group in grouped.items()
        if len(group) > 1
    }


def _preferred_title(rows: tuple[ResultRow, ...]) -> str:
    titles = Counter(
        row.title.strip()
        for row in rows
        if row.title.strip() and row.title.strip() not in {"-", "Metadata unavailable"}
    )
    if not titles:
        return "-"
    return sorted(titles.items(), key=lambda item: (-item[1], item[0].casefold()))[0][0]


def summarize_duplicate_groups(rows: Iterable[ResultRow]) -> tuple[DuplicateGroupSummary, ...]:
    """Build deterministic duplicate summaries from the current in-memory rows."""
    groups = duplicate_row_groups(rows)
    summaries: list[DuplicateGroupSummary] = []

    for title_id, group in groups.items():
        versions = tuple(
            sorted(
                {
                    row.version.strip()
                    for row in group
                    if row.version.strip() and row.version.strip() != "-"
                },
                key=str.casefold,
            )
        )
        statuses = Counter((row.status.strip().upper() or "UNKNOWN") for row in group)
        status_counts = tuple(sorted(statuses.items(), key=lambda item: item[0]))

        known_sizes = [max(0, int(row.size)) for row in group if row.size is not None]
        total_size = sum(known_sizes) if known_sizes else None
        if len(known_sizes) != len(group):
            same_size: bool | None = None
        else:
            same_size = len(set(known_sizes)) == 1

        summaries.append(
            DuplicateGroupSummary(
                title_id=title_id,
                title=_preferred_title(group),
                file_count=len(group),
                versions=versions,
                status_counts=status_counts,
                known_size_files=len(known_sizes),
                total_size=total_size,
                same_size=same_size,
            )
        )

    return tuple(sorted(summaries, key=lambda item: item.title_id.casefold()))
