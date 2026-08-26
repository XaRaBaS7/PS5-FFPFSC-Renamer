from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from ..library_export import ExportRow, export_csv, export_json


class LibraryExportMixin:
    """CSV/JSON export actions for library, visible and selected result scopes."""

    @staticmethod
    def _export_row(record) -> ExportRow:
        view = record.view
        return ExportRow(
            path=str(view.source),
            filename=view.source.name,
            title_id=view.title_id,
            title=view.title,
            version=view.version,
            size_bytes=view.size,
            proposed_output=view.output,
            status=view.status,
            duplicate_title_id=view.duplicate,
            change_state=view.change,
        )

    def _records_for_export(self, scope: str):
        if scope == "library":
            return list(self._all_records)
        if scope == "visible":
            return [
                self._row_records[row]
                for row in self.tree.get_children()
                if row in self._row_records
            ]
        if scope == "selected":
            return [
                self._row_records[row]
                for row in self.tree.selection()
                if row in self._row_records
            ]
        raise ValueError(scope)

    def _export_records(self, format_name: str, *, scope: str) -> None:
        records = self._records_for_export(scope)
        if not records:
            title = "Export selection" if scope == "selected" else "Export library"
            messagebox.showinfo(title, "There are no results in the requested export scope.", parent=self)
            return

        format_name = format_name.lower()
        if format_name not in {"csv", "json"}:
            raise ValueError(format_name)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        selected = filedialog.asksaveasfilename(
            title="Export FFPFSC results",
            parent=self,
            defaultextension=f".{format_name}",
            initialfile=f"PS5-FFPFSC-Renamer-{scope}-{stamp}.{format_name}",
            filetypes=[
                ("CSV files", "*.csv") if format_name == "csv" else ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return

        destination = Path(selected)
        rows = [self._export_row(record) for record in records]
        try:
            if format_name == "csv":
                export_csv(rows, destination)
            else:
                export_json(rows, destination)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return

        self.status_var.set(f"Exported {len(rows)} result(s) to {destination.name}")
        self._log("OK", f"Exported {len(rows)} {scope} result(s): {destination}")
        if messagebox.askyesno(
            "Export complete",
            f"Exported {len(rows)} result(s).\n\nShow the file in Explorer?",
            parent=self,
        ):
            self._show_in_explorer(destination)

    def _export_library(self, format_name: str, *, visible_only: bool) -> None:
        self._export_records(format_name, scope="visible" if visible_only else "library")

    def _export_selected(self, format_name: str) -> None:
        self._export_records(format_name, scope="selected")
