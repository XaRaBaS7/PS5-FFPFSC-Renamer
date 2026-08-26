from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ps5_ffpfsc_renamer.duplicate_manager import (
    duplicate_row_groups,
    summarize_duplicate_groups,
)
from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.ui.duplicate_manager_mixin import DuplicateManagerMixin


def _row(
    title_id: str,
    title: str,
    version: str,
    size: int | None,
    status: str = "READY",
) -> ResultRow:
    return ResultRow(
        source=Path(f"{title_id or 'missing'}-{version}.ffpfsc"),
        title_id=title_id,
        title=title,
        version=version,
        size=size,
        output="-",
        status=status,
    )


def test_duplicate_groups_are_case_insensitive_and_ignore_missing_ids() -> None:
    rows = [
        _row("ppsa01285", "Returnal", "01.000.000", 100),
        _row("PPSA01285", "Returnal", "01.001.000", 100),
        _row("PPSA11111", "Single", "01.000.000", 50),
        _row("-", "Unknown", "-", None),
    ]

    groups = duplicate_row_groups(rows)

    assert tuple(groups) == ("PPSA01285",)
    assert len(groups["PPSA01285"]) == 2


def test_duplicate_summary_is_deterministic_and_uses_in_memory_values() -> None:
    rows = [
        _row("ppsa01285", "Returnal", "01.001.000", 100, "UNCHANGED"),
        _row("PPSA01285", "Returnal", "01.000.000", 100, "READY"),
        _row("PPSA11111", "Single", "01.000.000", 50),
    ]

    summaries = summarize_duplicate_groups(rows)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.title_id == "PPSA01285"
    assert summary.title == "Returnal"
    assert summary.file_count == 2
    assert summary.versions == ("01.000.000", "01.001.000")
    assert summary.status_counts == (("READY", 1), ("UNCHANGED", 1))
    assert summary.total_size == 200
    assert summary.known_size_files == 2
    assert summary.same_size is True
    assert summary.size_state == "same size"


def test_duplicate_summary_never_claims_same_size_with_missing_size() -> None:
    summaries = summarize_duplicate_groups(
        [
            _row("PPSA01285", "Returnal", "01.000.000", 100),
            _row("PPSA01285", "Returnal", "01.000.000", None),
        ]
    )

    summary = summaries[0]
    assert summary.total_size == 100
    assert summary.known_size_files == 1
    assert summary.same_size is None
    assert summary.size_state == "size incomplete"


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Tree:
    def __init__(self) -> None:
        self.selected: tuple[str, ...] = ()
        self.focused = ""
        self.seen = ""

    def get_children(self, _item: str = "") -> tuple[str, ...]:
        return ("row-1", "row-2")

    def selection_set(self, *items: str) -> None:
        self.selected = tuple(items)

    def focus(self, item: str) -> None:
        self.focused = item

    def see(self, item: str) -> None:
        self.seen = item


class _SelectionHarness(DuplicateManagerMixin):
    FILTERS = ("ALL", "PROBLEMS", "DUPLICATES")

    def __init__(self) -> None:
        self.search_var = _Var("returnal")
        self.filter_var = _Var("ALL")
        self.status_var = _Var()
        self.tree = _Tree()
        self.render_count = 0

    def _render_records(self) -> None:
        self.render_count += 1


def test_select_duplicate_rows_focuses_filter_and_selects_rendered_rows() -> None:
    harness = _SelectionHarness()

    count = harness._select_duplicate_rows()

    assert count == 2
    assert harness.search_var.value == ""
    assert harness.filter_var.value == "DUPLICATES"
    assert harness.render_count == 1
    assert harness.tree.selected == ("row-1", "row-2")
    assert harness.tree.focused == "row-1"
    assert harness.status_var.value == "2 duplicate row(s) selected"


def test_select_problem_rows_uses_problem_filter() -> None:
    harness = _SelectionHarness()

    count = harness._select_problem_rows()

    assert count == 2
    assert harness.filter_var.value == "PROBLEMS"
    assert harness.status_var.value == "2 problem row(s) selected"


def test_select_filtered_rows_rejects_unknown_filter() -> None:
    harness = _SelectionHarness()

    with pytest.raises(ValueError, match="Unsupported selection filter"):
        harness._select_filtered_rows("BROKEN", label="row(s)")


class _FocusHarness(DuplicateManagerMixin):
    def __init__(self) -> None:
        self.search_var = _Var()
        self.filter_var = _Var("ALL")
        self.status_var = _Var()
        self.tree = _Tree()
        self.render_count = 0
        self._row_records = {
            "row-1": SimpleNamespace(
                view=_row("PPSA01285", "Returnal", "01.000.000", 100)
            ),
            "row-2": SimpleNamespace(
                view=_row("ppsa01285", "Returnal", "01.001.000", 100)
            ),
            "row-stray": SimpleNamespace(
                view=_row("PPSA99999", "Archive PPSA01285 copy", "01.000.000", 100)
            ),
        }

    def _render_records(self) -> None:
        self.render_count += 1


def test_focus_duplicate_group_selects_exact_title_id_only() -> None:
    harness = _FocusHarness()

    count = harness._focus_duplicate_group("ppsa01285")

    assert count == 2
    assert harness.search_var.value == "PPSA01285"
    assert harness.filter_var.value == "DUPLICATES"
    assert harness.render_count == 1
    assert harness.tree.selected == ("row-1", "row-2")
    assert harness.tree.focused == "row-1"
    assert harness.status_var.value == "Duplicate group PPSA01285: 2 file(s) selected"
