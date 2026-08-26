from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import ttk

from ..diagnostics import classify_reader_error
from ..library_view import (
    ResultRow,
    duplicate_title_ids,
    human_size,
    matches_filter,
    matches_search,
    safe_file_size,
)
from ..rename_plan import PlanStatus
from ..theme import COLORS
from ..workspace_models import LibraryRecord


class LibraryWorkspaceMixin:
    """Searchable/filterable multi-select library table extracted from gui_v9."""

    FILTERS = (
        "ALL",
        "READY",
        "UNCHANGED",
        "PARTIAL",
        "COLLISION",
        "INVALID",
        "ERROR",
        "ADDED",
        "CHANGED",
        "DUPLICATES",
    )

    def _build_table(self, parent) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(8, 0))

        ttk.Label(toolbar, text="Search", style="CardMuted.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        search = tk.Entry(
            toolbar,
            textvariable=self.search_var,
            bg="#211a2f",
            fg="#f4f0ff",
            insertbackground="#f4f0ff",
            selectbackground="#8b5cf6",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#3a304d",
            highlightcolor="#8b5cf6",
            relief="flat",
            font=("Segoe UI", 9),
            width=34,
        )
        search.pack(side="left", padx=(6, 12), ipady=5)

        ttk.Label(toolbar, text="Filter", style="CardMuted.TLabel").pack(side="left")
        self.filter_var = tk.StringVar(value="ALL")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=self.FILTERS,
            state="readonly",
            width=13,
            style="Performance.TCombobox",
        )
        filter_combo.pack(side="left", padx=(6, 0))

        self.result_count_var = tk.StringVar(value="0 results")
        ttk.Label(
            toolbar,
            textvariable=self.result_count_var,
            style="CardMuted.TLabel",
        ).pack(side="right")

        super()._build_table(parent)
        columns = ("file", "title_id", "title", "version", "size", "output", "status")
        self.tree.configure(columns=columns, selectmode="extended")
        headings = {
            "file": "Current file",
            "title_id": "Title ID",
            "title": "Title",
            "version": "Version",
            "size": "Size",
            "output": "Proposed output",
            "status": "Status",
        }
        widths = {
            "file": 300,
            "title_id": 105,
            "title": 230,
            "version": 100,
            "size": 85,
            "output": 330,
            "status": 95,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=70, anchor="w")
        self.tree.tag_configure("partial", foreground=COLORS["warning"])
        self.tree.tag_configure("added", foreground=COLORS["success"])
        self.tree.tag_configure("changed", foreground=COLORS["warning"])

        self.search_var.trace_add("write", lambda *_: self._render_records())
        self.filter_var.trace_add("write", lambda *_: self._render_records())
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", self._double_click, add="+")

    def _known_file_size(self, path) -> int | None:
        state = getattr(self, "_last_scan_file_states", {}).get(path)
        if state is not None:
            return int(state.size)
        return safe_file_size(path)

    def _record_model(self) -> list[LibraryRecord]:
        records: list[LibraryRecord] = []
        for item in self.plan:
            metadata = item.metadata
            records.append(
                LibraryRecord(
                    ResultRow(
                        source=item.source,
                        title_id=metadata.title_id,
                        title=metadata.title_name or "-",
                        version=metadata.content_version or metadata.master_version or "-",
                        size=self._known_file_size(item.source),
                        output=self._display_destination(item),
                        status=item.status.value.upper(),
                    ),
                    plan_item=item,
                )
            )

        for image, metadata, detail, inference_source, _code, friendly in self.partial_items:
            records.append(
                LibraryRecord(
                    ResultRow(
                        source=image,
                        title_id=metadata.title_id,
                        title=metadata.title_name or "-",
                        version="-",
                        size=self._known_file_size(image),
                        output="-",
                        status="PARTIAL",
                    ),
                    detail=detail,
                    friendly=friendly,
                    inference_source=inference_source,
                )
            )

        for image, detail in self.scan_errors:
            _code, friendly = classify_reader_error(detail)
            records.append(
                LibraryRecord(
                    ResultRow(
                        source=image,
                        title_id="-",
                        title="Metadata unavailable",
                        version="-",
                        size=self._known_file_size(image),
                        output="-",
                        status="ERROR",
                    ),
                    detail=detail,
                    friendly=friendly,
                )
            )

        duplicate_ids = duplicate_title_ids([record.view for record in records])
        result: list[LibraryRecord] = []
        for record in records:
            is_duplicate = record.view.title_id.upper() in duplicate_ids
            record.view = replace(record.view, duplicate=is_duplicate)
            result.append(record)
        return result

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        super()._rebuild_output_plan(option_change=option_change)
        self._all_records = self._record_model()
        self._duplicate_groups = {}
        for record in self._all_records:
            if record.view.duplicate and record.view.title_id != "-":
                self._duplicate_groups.setdefault(record.view.title_id.upper(), []).append(record)
        self._render_records()

    def _render_records(self) -> None:
        if not hasattr(self, "tree"):
            return
        query = self.search_var.get() if hasattr(self, "search_var") else ""
        selected_filter = self.filter_var.get() if hasattr(self, "filter_var") else "ALL"
        visible = [
            record
            for record in self._all_records
            if matches_search(record.view, query) and matches_filter(record.view, selected_filter)
        ]

        self._hide_tree_tooltip()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._row_plan_items.clear()
        self._row_sources.clear()
        self._row_tooltips.clear()
        self._row_records.clear()

        for record in visible:
            view = record.view
            tags = [view.status.lower()]
            if view.change:
                tags.append(view.change.lower())
            row = self.tree.insert(
                "",
                "end",
                values=(
                    self._display_source(view.source),
                    view.title_id,
                    view.title,
                    view.version,
                    human_size(view.size),
                    view.output,
                    view.status,
                ),
                tags=tuple(tags),
            )
            self._row_records[row] = record
            self._row_sources[row] = view.source
            if record.plan_item is not None:
                self._row_plan_items[row] = record.plan_item
                if record.plan_item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}:
                    self._row_tooltips[row] = (
                        f"{view.status}\n{self._friendly_reason(record.plan_item.reason)}\n"
                        f"Source: {self._display_source(view.source)}\n"
                        f"Target: {record.plan_item.destination}"
                    )
            elif view.status == "PARTIAL":
                self._row_tooltips[row] = (
                    f"PARTIAL\n{record.friendly}\n"
                    f"Detected from: {record.inference_source}\n"
                    "The displayed metadata was not verified inside the FFPFSC. "
                    "Automatic rename remains disabled for this row."
                )
            elif view.status == "ERROR":
                self._row_tooltips[row] = (
                    f"ERROR\n{record.friendly}\n"
                    "Right-click and choose Run diagnostics for technical details."
                )

        self.result_count_var.set(f"{len(visible)} of {len(self._all_records)} results")

    def _show_tooltip_text(self, row: str, text: str) -> None:
        if self._tooltip_window is not None and self._tooltip_row == row:
            return
        self._hide_tree_tooltip()
        self._tooltip_row = row
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(
            tooltip,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["accent"],
        )
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame,
            text=text,
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
            wraplength=470,
        ).pack()
        tooltip.wm_geometry(
            f"+{self.tree.winfo_pointerx() + 14}+{self.tree.winfo_pointery() + 16}"
        )
        self._tooltip_window = tooltip

    def _on_tree_motion(self, event) -> None:
        row = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not row:
            self._hide_tree_tooltip()
            return
        record = self._row_records.get(row)
        if record is None:
            self._hide_tree_tooltip()
            return

        if column == "#1" and record.view.change:
            label = "NEW FILE" if record.view.change == "ADDED" else "CHANGED FILE"
            self._show_tooltip_text(
                row,
                f"{label}\nDetected by comparing this successful scan with the previous saved library baseline.",
            )
            return
        if column == "#7" and row in self._row_tooltips:
            self._show_tooltip_text(row, self._row_tooltips[row])
            return
        if column == "#2" and record.view.duplicate:
            group = self._duplicate_groups.get(record.view.title_id.upper(), [])
            self._show_tooltip_text(
                row,
                f"DUPLICATE TITLE ID\n{record.view.title_id} appears in {len(group)} files.\n"
                "Right-click and choose Compare duplicates to inspect paths, sizes and quick fingerprints.",
            )
            return
        self._hide_tree_tooltip()
