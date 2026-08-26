from __future__ import annotations

import re
import tkinter as tk

from ..library_view import human_size
from ..workspace_models import LibraryRecord


class SortableResultsMixin:
    """Sortable result columns and visible-result size summary."""

    SORTABLE_COLUMNS = {
        "file": "Current file",
        "title_id": "Title ID",
        "title": "Title",
        "version": "Version",
        "size": "Size",
        "output": "Proposed output",
        "status": "Status",
    }
    STATUS_ORDER = {
        "READY": 0,
        "UNCHANGED": 1,
        "PARTIAL": 2,
        "COLLISION": 3,
        "INVALID": 4,
        "ERROR": 5,
        "OFFLINE": 6,
    }

    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        for column, label in self.SORTABLE_COLUMNS.items():
            self.tree.heading(
                column,
                text=label,
                command=lambda selected=column: self._sort_by_column(selected),
            )
        self._refresh_sort_headings()

    def _render_records(self) -> None:
        super()._render_records()
        self._apply_tree_sort()
        if hasattr(self, "result_count_var"):
            visible = [
                self._row_records[row]
                for row in self.tree.get_children()
                if row in self._row_records
            ]
            visible_size = sum(record.view.size or 0 for record in visible)
            self.result_count_var.set(
                f"{len(visible)} of {len(self._all_records)} results • {human_size(visible_size)}"
            )

    @staticmethod
    def _version_key(value: str) -> tuple[tuple[int, ...], str]:
        numbers = tuple(int(part) for part in re.findall(r"\d+", value))
        return numbers, value.casefold()

    def _sort_key(self, record: LibraryRecord, column: str):
        view = record.view
        if column == "size":
            return view.size if view.size is not None else -1
        if column == "version":
            return self._version_key(view.version)
        if column == "status":
            return self.STATUS_ORDER.get(view.status, 99), view.status.casefold()
        if column == "title_id":
            return view.title_id.casefold()
        if column == "title":
            return view.title.casefold()
        if column == "output":
            return view.output.casefold()
        return self._display_source(view.source).casefold()

    def _apply_tree_sort(self) -> None:
        if not hasattr(self, "tree") or not hasattr(self, "_row_records"):
            return
        rows = [row for row in self.tree.get_children() if row in self._row_records]
        rows.sort(
            key=lambda row: self._sort_key(self._row_records[row], self._sort_column),
            reverse=self._sort_descending,
        )
        for index, row in enumerate(rows):
            self.tree.move(row, "", index)
        self._refresh_sort_headings()

    def _sort_by_column(self, column: str) -> None:
        if column not in self.SORTABLE_COLUMNS:
            return
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._apply_tree_sort()
        self._queue_save_preferences()

    def _refresh_sort_headings(self) -> None:
        if not hasattr(self, "tree"):
            return
        for column, label in self.SORTABLE_COLUMNS.items():
            arrow = ""
            if column == self._sort_column:
                arrow = " ▼" if self._sort_descending else " ▲"
            try:
                self.tree.heading(column, text=label + arrow)
            except tk.TclError:
                pass
