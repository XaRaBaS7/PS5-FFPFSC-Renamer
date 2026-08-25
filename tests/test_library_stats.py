from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.library_stats import summarize_library
from ps5_ffpfsc_renamer.library_view import ResultRow


def row(name: str, title_id: str, size: int | None, status: str, duplicate: bool = False) -> ResultRow:
    return ResultRow(
        source=Path(name),
        title_id=title_id,
        title=name,
        version="1.0",
        size=size,
        output=name,
        status=status,
        duplicate=duplicate,
    )


def test_library_stats_counts_status_size_and_duplicates():
    stats = summarize_library(
        [
            row("A", "PPSA00001", 100, "READY"),
            row("A-copy", "PPSA00001", 120, "COLLISION", duplicate=True),
            row("B", "PPSA00002", 300, "UNCHANGED"),
            row("Unknown", "-", None, "ERROR"),
        ]
    )

    assert stats.total_files == 4
    assert stats.total_size == 520
    assert stats.known_size_files == 3
    assert stats.average_size == 173
    assert stats.unique_title_ids == 2
    assert stats.duplicate_groups == 1
    assert stats.duplicate_files == 2
    assert dict(stats.status_counts) == {
        "READY": 1,
        "UNCHANGED": 1,
        "COLLISION": 1,
        "ERROR": 1,
    }
    assert [item.title for item in stats.largest[:2]] == ["B", "A-copy"]


def test_library_stats_empty_library_is_safe():
    stats = summarize_library([])
    assert stats.total_files == 0
    assert stats.total_size == 0
    assert stats.average_size is None
    assert stats.largest == ()
