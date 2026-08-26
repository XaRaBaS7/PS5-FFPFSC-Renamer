from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.desktop import RenamerApp
from ps5_ffpfsc_renamer.library_status import (
    RESULT_FILTERS,
    configured_root_statuses,
    summarize_library_status,
)
from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.root_health import RootStatus, root_key


def _row(
    name: str,
    *,
    title_id: str,
    status: str = "READY",
    duplicate: bool = False,
    change: str = "",
) -> ResultRow:
    return ResultRow(
        source=Path(name),
        title_id=title_id,
        title=name,
        version="01.000.000",
        size=100,
        output=f"renamed-{name}",
        status=status,
        duplicate=duplicate,
        change=change,
    )


def test_result_filters_expose_health_change_and_offline_views() -> None:
    assert RESULT_FILTERS == RenamerApp.FILTERS
    assert "HEALTHY" in RESULT_FILTERS
    assert "PROBLEMS" in RESULT_FILTERS
    assert "ADDED" in RESULT_FILTERS
    assert "CHANGED" in RESULT_FILTERS
    assert "OFFLINE" in RESULT_FILTERS


def test_library_status_summary_uses_in_memory_counts() -> None:
    rows = [
        _row("a.ffpfsc", title_id="PPSA00001", duplicate=True, change="ADDED"),
        _row("b.ffpfsc", title_id="ppsa00001", duplicate=True, change="CHANGED"),
        _row("c.ffpfsc", title_id="PPSA00002", status="PARTIAL"),
        _row("d.ffpfsc", title_id="PPSA00003", status="ERROR"),
        _row("e.ffpfsc", title_id="PPSA00004", status="OFFLINE"),
    ]
    roots = [
        RootStatus(Path("G:/PS5"), "ONLINE", "available"),
        RootStatus(Path("Z:/Archive"), "OFFLINE", "unavailable"),
    ]

    summary = summarize_library_status(
        rows,
        visible_count=4,
        selected_count=2,
        root_count=2,
        root_statuses=roots,
    )

    assert summary.visible_count == 4
    assert summary.selected_count == 2
    assert summary.online_root_count == 1
    assert summary.offline_count == 1
    assert summary.problem_count == 2
    assert summary.duplicate_group_count == 1
    assert summary.added_count == 1
    assert summary.changed_count == 1
    assert summary.text() == (
        "4 visible • 2 selected • roots 1/2 online • 1 offline • 2 problems • "
        "1 duplicate group • changes +1 / ~1"
    )


def test_offline_rows_are_not_counted_as_metadata_problems() -> None:
    summary = summarize_library_status(
        [_row("offline.ffpfsc", title_id="PPSA00001", status="OFFLINE")],
        visible_count=1,
        selected_count=0,
        root_count=1,
        root_statuses=[RootStatus(Path("Z:/Archive"), "OFFLINE", "unavailable")],
    )

    assert summary.offline_count == 1
    assert summary.problem_count == 0
    assert "1 offline" in summary.text()
    assert "0 problems" in summary.text()


def test_configured_root_statuses_ignore_removed_roots() -> None:
    configured = Path("G:/PS5")
    removed = Path("Z:/Archive")
    statuses = {
        root_key(configured): RootStatus(configured, "ONLINE", "available"),
        root_key(removed): RootStatus(removed, "ONLINE", "stale"),
    }

    current = configured_root_statuses([configured], statuses)

    assert current == (statuses[root_key(configured)],)


def test_library_status_summary_handles_empty_workspace() -> None:
    summary = summarize_library_status(
        [],
        visible_count=0,
        selected_count=0,
        root_count=0,
        root_statuses=[],
    )

    assert summary.text() == (
        "0 visible • 0 selected • roots 0 • 0 problems • 0 duplicate groups"
    )
