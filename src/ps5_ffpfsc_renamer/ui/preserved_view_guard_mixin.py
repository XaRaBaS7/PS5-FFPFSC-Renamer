from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from ..theme import COLORS
from ..workspace_models import LibraryRecord


class PreservedViewGuardMixin:
    """Keep preserved scan rows read-only until their filesystem state is fresh."""

    @staticmethod
    def _source_key(path: Path) -> str:
        return str(path).casefold()

    def _record_requires_live_filesystem(self, record: LibraryRecord) -> bool:
        return bool(getattr(self, "_scan_view_stale", False)) or record.view.status.upper() == "OFFLINE"

    def _offline_source_keys(self) -> set[str]:
        return {
            self._source_key(record.view.source)
            for record in getattr(self, "_all_records", ())
            if record.view.status.upper() == "OFFLINE"
        }

    def _path_requires_live_filesystem(self, path: Path) -> bool:
        if getattr(self, "_scan_view_stale", False):
            return True
        return self._source_key(path) in self._offline_source_keys()

    def _preserved_view_message(self) -> str:
        if getattr(self, "_scan_view_stale", False):
            return (
                "The latest library scan did not complete. These results were restored from the previous "
                "successful scan and are read-only until a fresh scan completes successfully."
            )
        return (
            "One or more selected rows belong to a library root that is currently unavailable. "
            "Preserved OFFLINE rows are read-only until that root is scanned successfully again."
        )

    def _show_preserved_view_notice(self, title: str) -> None:
        messagebox.showinfo(title, self._preserved_view_message(), parent=self)

    def _activate_details_record(self, record: LibraryRecord, *, force: bool = False) -> None:
        if not self._record_requires_live_filesystem(record):
            super()._activate_details_record(record, force=force)
            return

        try:
            self._cancel_pending_details()
        except Exception:
            pass
        self._details_record = None
        self._details_generation = int(getattr(self, "_details_generation", 0)) + 1
        message = self._preserved_view_message()
        if getattr(self, "_details_status_var", None) is not None:
            self._details_status_var.set("Preserved result — details not loaded")
        if getattr(self, "_details_toggle_button", None) is not None:
            try:
                self._details_toggle_button.configure(state="disabled")
            except Exception:
                pass
        try:
            self._set_details_json(message)
            self._reset_details_icon("OFFLINE\nnot loaded")
        except Exception:
            pass
        try:
            self.status_var.set("Preserved result selected — filesystem actions disabled")
        except Exception:
            pass

    def _prefetch_selected_details(self) -> None:
        records = list(self._selected_records())
        if any(self._record_requires_live_filesystem(record) for record in records):
            self._show_preserved_view_notice("Preload game details")
            return
        super()._prefetch_selected_details()

    def _run_diagnostics(self, path: Path) -> None:
        if self._path_requires_live_filesystem(path):
            self._show_preserved_view_notice("Diagnostics")
            return
        super()._run_diagnostics(path)

    def _analyze_paths(self, paths: list[Path]) -> None:
        if any(self._path_requires_live_filesystem(path) for path in paths):
            self._show_preserved_view_notice("Analyze again")
            return
        super()._analyze_paths(paths)

    def _compare_duplicates(self, title_id: str) -> None:
        group = list(getattr(self, "_duplicate_groups", {}).get(title_id.upper(), ()))
        if getattr(self, "_scan_view_stale", False) or any(
            record.view.status.upper() == "OFFLINE" for record in group
        ):
            self._show_preserved_view_notice("Compare duplicates")
            return
        super()._compare_duplicates(title_id)

    def _double_click(self, event) -> str:
        row = self.tree.identify_row(event.y)
        record = self._row_records.get(row)
        if record is not None and self._record_requires_live_filesystem(record):
            self.status_var.set("Preserved result — complete a fresh scan before opening details")
            return "break"
        return super()._double_click(event)

    def _show_context_menu(self, event) -> str:
        row = self.tree.identify_row(event.y)
        if not row:
            return "break"
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        records = list(self._selected_records())
        if not records or not any(
            self._record_requires_live_filesystem(record) for record in records
        ):
            return super()._show_context_menu(event)

        self._hide_tree_tooltip()
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
        menu.add_command(
            label="Preserved results — filesystem actions disabled",
            state="disabled",
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
            command=lambda values=[str(record.view.source) for record in records]: self._copy_text(
                "\n".join(values)
            ),
        )
        menu.add_command(
            label="Copy unique Title IDs / PPSA",
            command=lambda chosen=records: self._copy_unique_title_ids(chosen),
        )
        menu.add_command(
            label="Copy Title ID + game title",
            command=lambda chosen=records: self._copy_title_id_title_lines(chosen),
        )
        menu.add_separator()
        menu.add_command(label="Retry library scan", command=self._scan)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"
