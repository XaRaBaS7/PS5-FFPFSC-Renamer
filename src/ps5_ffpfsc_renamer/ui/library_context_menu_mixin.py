from __future__ import annotations

import tkinter as tk

from ..rename_plan import PlanStatus
from ..theme import COLORS
from ..workspace_models import LibraryRecord


class LibraryContextMenuMixin:
    """Context actions for single and multi-selection result rows."""

    def _selected_records(self) -> list[LibraryRecord]:
        return [
            self._row_records[row]
            for row in self.tree.selection()
            if row in self._row_records
        ]

    @staticmethod
    def _selected_title_ids(records: list[LibraryRecord]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for record in records:
            value = record.view.title_id.strip()
            if not value or value == "-":
                continue
            normalized = value.upper()
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    @staticmethod
    def _selected_catalog_lines(records: list[LibraryRecord]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for record in records:
            value = record.view.title_id.strip()
            if not value or value == "-":
                continue
            normalized = value.upper()
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            title = record.view.title.strip() or "-"
            result.append(f"{normalized} - {title}")
        return result

    def _copy_unique_title_ids(self, records: list[LibraryRecord]) -> None:
        values = self._selected_title_ids(records)
        if values:
            self._copy_text("\n".join(values))

    def _copy_title_id_title_lines(self, records: list[LibraryRecord]) -> None:
        values = self._selected_catalog_lines(records)
        if values:
            self._copy_text("\n".join(values))

    def _show_context_menu(self, event) -> str:
        row = self.tree.identify_row(event.y)
        if not row:
            return "break"
        self._hide_tree_tooltip()
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        records = self._selected_records()
        if not records:
            return "break"

        menu = tk.Menu(
            self,
            tearoff=False,
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            activebackground=COLORS["accent"],
            activeforeground="#ffffff",
            bd=1,
            relief="solid",
        )

        if len(records) > 1:
            ready = [
                record.plan_item
                for record in records
                if record.plan_item and record.plan_item.status is PlanStatus.READY
            ]
            menu.add_command(
                label=f"Rename selected using current plan ({len(ready)} ready)",
                command=lambda items=ready: self._rename_selected_items(items),
                state="normal" if ready else "disabled",
            )
            menu.add_command(
                label=f"Analyze selected again ({len(records)})",
                command=lambda paths=[record.view.source for record in records]: self._analyze_paths(paths),
            )
            menu.add_command(
                label=f"Preload game details ({len(records)})",
                command=self._prefetch_selected_details,
            )
            menu.add_separator()
            menu.add_command(
                label="Export selected as CSV...",
                command=lambda: self._export_selected("csv"),
            )
            menu.add_command(
                label="Export selected as JSON...",
                command=lambda: self._export_selected("json"),
            )
            menu.add_separator()
            menu.add_command(
                label="Copy selected paths",
                command=lambda values=[str(record.view.source) for record in records]: self._copy_text("\n".join(values)),
            )
            menu.add_command(
                label="Copy unique Title IDs / PPSA",
                command=lambda chosen=records: self._copy_unique_title_ids(chosen),
            )
            menu.add_command(
                label="Copy Title ID + game title",
                command=lambda chosen=records: self._copy_title_id_title_lines(chosen),
            )
            menu.add_command(
                label=f"Move selected to Recycle Bin... ({len(records)})",
                command=lambda chosen=records: self._delete_records(chosen),
            )
        else:
            record = records[0]
            item = record.plan_item
            if item is not None:
                menu.add_command(
                    label="Rename using current plan",
                    command=lambda selected=item: self._rename_selected_plan(selected),
                    state="normal" if item.status is PlanStatus.READY else "disabled",
                )
            menu.add_command(
                label="Rename file manually...",
                command=lambda path=record.view.source: self._manual_rename(path),
            )
            menu.add_separator()
            menu.add_command(
                label="Show in Explorer",
                command=lambda path=record.view.source: self._show_in_explorer(path),
            )
            menu.add_command(
                label="Open folder",
                command=lambda path=record.view.source: self._open_folder(path),
            )
            menu.add_command(
                label="Run diagnostics",
                command=lambda path=record.view.source: self._run_diagnostics(path),
            )
            menu.add_separator()
            menu.add_command(
                label="Copy full path",
                command=lambda path=record.view.source: self._copy_text(str(path)),
            )
            if record.view.title_id != "-":
                menu.add_command(
                    label="Copy Title ID / PPSA",
                    command=lambda value=record.view.title_id: self._copy_text(value),
                )
            menu.add_command(
                label="Show details",
                command=lambda selected=record: self._show_record_details(selected),
            )
            menu.add_command(
                label="Analyze again",
                command=lambda path=record.view.source: self._analyze_paths([path]),
            )
            if record.view.duplicate:
                menu.add_command(
                    label=f"Compare duplicates ({len(self._duplicate_groups.get(record.view.title_id.upper(), []))})",
                    command=lambda title_id=record.view.title_id: self._compare_duplicates(title_id),
                )
            if item is not None and item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}:
                menu.add_command(
                    label="Why blocked?",
                    command=lambda selected=item: self._show_block_reason(selected),
                )
            menu.add_separator()
            menu.add_command(
                label="Move to Recycle Bin...",
                command=lambda chosen=[record]: self._delete_records(chosen),
            )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _double_click(self, event) -> str:
        row = self.tree.identify_row(event.y)
        record = self._row_records.get(row)
        if record is None:
            return "break"
        if record.view.status in {"PARTIAL", "ERROR"}:
            self._run_diagnostics(record.view.source)
        else:
            self._show_record_details(record)
        return "break"
