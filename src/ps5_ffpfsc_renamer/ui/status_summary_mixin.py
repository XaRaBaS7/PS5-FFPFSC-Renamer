from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..library_status import (
    RESULT_FILTERS,
    configured_root_statuses,
    summarize_library_status,
)


class StatusSummaryMixin:
    """Persistent library-status summary backed only by current in-memory state."""

    FILTERS = RESULT_FILTERS

    def _build_footer(self, parent: ttk.Frame) -> None:
        self.library_status_var = tk.StringVar(
            value="0 visible • 0 selected • roots 0 • 0 problems • 0 duplicate groups"
        )
        summary = ttk.Frame(parent)
        summary.pack(fill="x", pady=(5, 2))
        ttk.Label(
            summary,
            textvariable=self.library_status_var,
            style="CardMuted.TLabel",
        ).pack(side="left")
        super()._build_footer(parent)
        if hasattr(self, "tree"):
            self.tree.bind(
                "<<TreeviewSelect>>",
                self._on_library_status_selection,
                add="+",
            )
        self._refresh_library_status_summary()

    def _render_records(self) -> None:
        super()._render_records()
        self._refresh_library_status_summary()

    def _update_root_summary(self) -> None:
        super()._update_root_summary()
        self._refresh_library_status_summary()

    def _on_library_status_selection(self, _event=None) -> None:
        self._refresh_library_status_summary()

    def _refresh_library_status_summary(self) -> None:
        variable = getattr(self, "library_status_var", None)
        if variable is None:
            return

        records = tuple(
            record.view for record in getattr(self, "_all_records", ())
        )
        tree = getattr(self, "tree", None)
        if tree is None:
            visible_count = 0
            selected_count = 0
        else:
            try:
                visible_count = len(tree.get_children(""))
                selected_count = len(tree.selection())
            except tk.TclError:
                return

        roots = tuple(getattr(self, "library_roots", ()))
        root_statuses = configured_root_statuses(
            roots,
            getattr(self, "_root_statuses", {}),
        )
        status = summarize_library_status(
            records,
            visible_count=visible_count,
            selected_count=selected_count,
            root_count=len(roots),
            root_statuses=root_statuses,
        )
        variable.set(status.text())
