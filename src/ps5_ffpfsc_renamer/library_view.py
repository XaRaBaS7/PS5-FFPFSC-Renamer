from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResultRow:
    source: Path
    title_id: str
    title: str
    version: str
    size: int | None
    output: str
    status: str
    duplicate: bool = False


def human_size(size: int | None) -> str:
    if size is None:
        return "-"
    value = float(max(0, size))
    units = ("B", "KB", "MB", "GB", "TB")
    unit = units[0]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            break
        value /= 1024.0
    if unit == "B":
        return f"{int(value)} B"
    return f"{value:.1f} {unit}"


def safe_file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def matches_search(row: ResultRow, query: str) -> bool:
    query = query.strip().casefold()
    if not query:
        return True
    haystack = "\n".join(
        (
            str(row.source),
            row.title_id,
            row.title,
            row.version,
            row.output,
            row.status,
        )
    ).casefold()
    return all(token in haystack for token in query.split())


def matches_filter(row: ResultRow, selected: str) -> bool:
    selected = selected.strip().upper() or "ALL"
    if selected == "ALL":
        return True
    if selected == "DUPLICATES":
        return row.duplicate
    return row.status.upper() == selected


def duplicate_title_ids(rows: list[ResultRow]) -> set[str]:
    counts: dict[str, int] = {}
    for row in rows:
        title_id = row.title_id.strip().upper()
        if not title_id or title_id == "-":
            continue
        counts[title_id] = counts.get(title_id, 0) + 1
    return {title_id for title_id, count in counts.items() if count > 1}
