from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from ..rename_manifest import build_manifest_rows, export_manifest_csv, export_manifest_json


class RenameManifestMixin:
    """Read-only export of the current rename plan before filesystem changes."""

    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return

        file_menu = self._find_menu_cascade(menubar, "File")
        if file_menu is None:
            return
        export_menu = self._find_menu_cascade(file_menu, "Export")
        if export_menu is None:
            return

        try:
            export_menu.add_separator()
            export_menu.add_command(
                label="Rename plan (dry-run) as CSV...",
                command=lambda: self._export_rename_manifest("csv"),
            )
            export_menu.add_command(
                label="Rename plan (dry-run) as JSON...",
                command=lambda: self._export_rename_manifest("json"),
            )
        except tk.TclError:
            return

    def _find_menu_cascade(self, menu: tk.Menu, label: str) -> tk.Menu | None:
        end = menu.index("end")
        if end is None:
            return None
        for index in range(int(end) + 1):
            try:
                if menu.type(index) != "cascade":
                    continue
                if str(menu.entrycget(index, "label")) != label:
                    continue
                child = self.nametowidget(menu.entrycget(index, "menu"))
                return child if isinstance(child, tk.Menu) else None
            except tk.TclError:
                continue
        return None

    def _export_rename_manifest(self, format_name: str) -> None:
        items = list(getattr(self, "plan", []))
        if not items:
            messagebox.showinfo(
                "Export rename plan",
                "There is no current rename plan to export. Scan the library first.",
                parent=self,
            )
            return

        format_name = format_name.lower()
        if format_name not in {"csv", "json"}:
            raise ValueError(format_name)

        rows = build_manifest_rows(items)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        selected = filedialog.asksaveasfilename(
            title="Export rename plan (dry-run)",
            parent=self,
            defaultextension=f".{format_name}",
            initialfile=f"PS5-FFPFSC-Renamer-plan-{stamp}.{format_name}",
            filetypes=[
                ("CSV files", "*.csv") if format_name == "csv" else ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return

        destination = Path(selected)
        try:
            if format_name == "csv":
                export_manifest_csv(rows, destination)
            else:
                export_manifest_json(rows, destination)
        except OSError as exc:
            messagebox.showerror("Export rename plan failed", str(exc), parent=self)
            return

        ready = sum(1 for row in rows if row.status == "READY")
        blocked = sum(1 for row in rows if row.status in {"COLLISION", "INVALID"})
        self.status_var.set(
            f"Dry-run rename manifest exported: {len(rows)} row(s), {ready} ready, {blocked} blocked"
        )
        try:
            self._log(
                "INFO",
                f"Rename manifest exported: {destination.name} • {len(rows)} row(s) • "
                f"READY {ready} • blocked {blocked}",
            )
        except Exception:
            pass
