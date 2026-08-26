from __future__ import annotations

from types import SimpleNamespace

import pytest

from ps5_ffpfsc_renamer.ui.scan_diff_mixin import ScanDiffMixin


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

    def selection_set(self, *rows: str) -> None:
        self.selected = tuple(rows)

    def focus(self, row: str) -> None:
        self.focused = row

    def see(self, row: str) -> None:
        self.seen = row


class _Harness(ScanDiffMixin):
    def __init__(self) -> None:
        self.search_var = _Var("returnal")
        self.filter_var = _Var("ALL")
        self.status_var = _Var()
        self.tree = _Tree()
        self._all = {
            "row-added": SimpleNamespace(view=SimpleNamespace(change="ADDED")),
            "row-changed": SimpleNamespace(view=SimpleNamespace(change="CHANGED")),
            "row-normal": SimpleNamespace(view=SimpleNamespace(change="")),
        }
        self._row_records = dict(self._all)

    def _render_records(self) -> None:
        selected_filter = self.filter_var.get()
        if selected_filter in {"ADDED", "CHANGED"}:
            self._row_records = {
                row: record
                for row, record in self._all.items()
                if record.view.change == selected_filter
            }
        else:
            self._row_records = dict(self._all)


def test_select_added_rows_uses_existing_change_markers_only() -> None:
    harness = _Harness()

    count = harness._select_added_rows()

    assert count == 1
    assert harness.search_var.value == ""
    assert harness.filter_var.value == "ADDED"
    assert harness.tree.selected == ("row-added",)
    assert harness.status_var.value == "1 added row(s) selected"


def test_select_changed_rows_uses_changed_filter() -> None:
    harness = _Harness()

    count = harness._select_changed_rows()

    assert count == 1
    assert harness.filter_var.value == "CHANGED"
    assert harness.tree.selected == ("row-changed",)
    assert harness.status_var.value == "1 changed row(s) selected"


def test_select_all_scan_changes_keeps_normal_rows_unselected() -> None:
    harness = _Harness()

    count = harness._select_all_scan_change_rows()

    assert count == 2
    assert harness.filter_var.value == "ALL"
    assert harness.tree.selected == ("row-added", "row-changed")
    assert harness.status_var.value == "2 added/changed row(s) selected"


def test_scan_change_selection_rejects_unknown_state() -> None:
    harness = _Harness()

    with pytest.raises(ValueError, match="ADDED and CHANGED only"):
        harness._select_scan_change_rows({"REMOVED"}, label="row(s)")
