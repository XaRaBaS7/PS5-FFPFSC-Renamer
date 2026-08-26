from __future__ import annotations

import os
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from ..rename_plan import PlanStatus, RenamePlanItem


class ResultActionsMixin:
    """Shared result-row state, tooltips and desktop path actions."""

    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        self._row_plan_items: dict[str, RenamePlanItem] = {}
        self._row_sources: dict[str, Path] = {}
        self._row_tooltips: dict[str, str] = {}
        self._tooltip_window: tk.Toplevel | None = None
        self._tooltip_row: str | None = None
        self.tree.bind("<Motion>", self._on_tree_motion, add="+")
        self.tree.bind("<Leave>", self._hide_tree_tooltip, add="+")
        self.tree.bind("<ButtonPress>", self._hide_tree_tooltip, add="+")

    @staticmethod
    def _friendly_reason(reason: str) -> str:
        explanations = {
            "duplicate file target": "Another scanned file would be renamed to the same destination file.",
            "duplicate folder target": "Another scanned file would use the same destination folder.",
            "target folder already exists": "The destination folder already exists. The program will not merge or overwrite it.",
            "target file already exists": "The destination file already exists. The program will not overwrite it.",
            "folder target is occupied by a file": "A file already exists where the destination folder would need to be created.",
            "source missing": "The source .ffpfsc file can no longer be found.",
            "source folder missing": "The source folder can no longer be found.",
            "selected library root cannot be renamed": "The selected library root is protected and will never be renamed.",
        }
        if reason in explanations:
            return explanations[reason]
        if reason.startswith("Smart folder handling requires exactly one .ffpfsc"):
            return (
                "Smart folder handling cannot safely rename this folder because it does not contain "
                "exactly one .ffpfsc file."
            )
        return reason[:1].upper() + reason[1:] if reason else "Blocked by the safety checks."

    def _tooltip_for_item(self, item: RenamePlanItem) -> str | None:
        if item.status not in {PlanStatus.COLLISION, PlanStatus.INVALID}:
            return None
        return "\n".join(
            (
                item.status.value.upper(),
                self._friendly_reason(item.reason),
                f"Source: {self._display_source(item.source)}",
                f"Target: {item.destination}",
            )
        )

    def _hide_tree_tooltip(self, _event=None) -> None:
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except tk.TclError:
                pass
        self._tooltip_window = None
        self._tooltip_row = None

    @staticmethod
    def _show_in_explorer(path: Path) -> None:
        path = path.resolve(strict=False)
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])

    @staticmethod
    def _open_folder(path: Path) -> None:
        folder = path.resolve(strict=False).parent
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.status_var.set("Copied to clipboard")

    def _show_block_reason(self, item: RenamePlanItem) -> None:
        text = self._tooltip_for_item(item) or "This file is not blocked."
        messagebox.showinfo("Why blocked?", text, parent=self)
