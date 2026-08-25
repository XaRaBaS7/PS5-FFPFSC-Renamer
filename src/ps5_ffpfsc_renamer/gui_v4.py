from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .gui_v3 import RenamerApp as RenamerAppV3
from .rename_plan import PlanStatus, RenamePlanItem
from .theme import COLORS


class RenamerApp(RenamerAppV3):
    """GUI refinements for clearer scan results and collision diagnostics."""

    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        # Give enough room to distinguish files with the same basename that
        # live in different folders. Status stays compact; details are shown
        # on hover so the results table remains easy to scan.
        self.tree.column("file", width=300, minwidth=180, anchor="w")
        self.tree.column("title", width=250, minwidth=150, anchor="w")
        self.tree.column("output", width=330, minwidth=180, anchor="w")
        self.tree.column("status", width=105, minwidth=90, anchor="w")

        self._row_tooltips: dict[str, str] = {}
        self._tooltip_window: tk.Toplevel | None = None
        self._tooltip_row: str | None = None
        self.tree.bind("<Motion>", self._on_tree_motion, add="+")
        self.tree.bind("<Leave>", self._hide_tree_tooltip, add="+")
        self.tree.bind("<ButtonPress>", self._hide_tree_tooltip, add="+")

    def _display_source(self, source: Path) -> str:
        """Show a path relative to the selected library whenever possible."""
        root_text = self.folder_var.get().strip()
        if root_text:
            try:
                root = Path(root_text).expanduser().resolve()
                return str(source.resolve().relative_to(root))
            except (OSError, ValueError):
                pass
        return source.name

    @staticmethod
    def _friendly_reason(reason: str) -> str:
        explanations = {
            "duplicate file target": (
                "Another scanned file would be renamed to the same destination file."
            ),
            "duplicate folder target": (
                "Another scanned file would use the same destination folder."
            ),
            "target folder already exists": (
                "The destination folder already exists. The program will not merge or overwrite it."
            ),
            "target file already exists": (
                "The destination file already exists. The program will not overwrite it."
            ),
            "folder target is occupied by a file": (
                "A file already exists where the destination folder would need to be created."
            ),
            "source missing": "The source .ffpfsc file can no longer be found.",
            "source folder missing": "The source folder can no longer be found.",
            "selected library root cannot be renamed": (
                "The selected library root is protected and will never be renamed."
            ),
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

        lines = [item.status.value.upper(), self._friendly_reason(item.reason)]
        lines.append(f"Source: {self._display_source(item.source)}")

        try:
            root_text = self.folder_var.get().strip()
            if root_text:
                root = Path(root_text).expanduser().resolve()
                target = item.destination.resolve().relative_to(root)
                lines.append(f"Target: {target}")
            else:
                lines.append(f"Target: {item.destination}")
        except (OSError, ValueError):
            lines.append(f"Target: {item.destination}")

        return "\n".join(lines)

    def _on_tree_motion(self, event) -> None:
        row = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        # Status is the sixth visible column (#6). Only show the diagnostic
        # tooltip when hovering that cell, keeping normal table navigation clean.
        if not row or column != "#6" or row not in self._row_tooltips:
            self._hide_tree_tooltip()
            return

        if self._tooltip_window is not None and self._tooltip_row == row:
            return

        self._hide_tree_tooltip()
        self._tooltip_row = row
        text = self._row_tooltips[row]

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
            wraplength=430,
        ).pack()

        x = self.tree.winfo_pointerx() + 14
        y = self.tree.winfo_pointery() + 16
        tooltip.wm_geometry(f"+{x}+{y}")
        self._tooltip_window = tooltip

    def _hide_tree_tooltip(self, _event=None) -> None:
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except tk.TclError:
                pass
        self._tooltip_window = None
        self._tooltip_row = None

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        # Let the established planner update rows, counters and button state.
        super()._rebuild_output_plan(option_change=option_change)

        self._hide_tree_tooltip()
        self._row_tooltips.clear()
        rows = list(self.tree.get_children())
        row_index = 0

        # Rows are inserted by the parent in the same order as self.plan.
        for item in self.plan:
            if row_index >= len(rows):
                break
            row = rows[row_index]
            values = list(self.tree.item(row, "values"))
            if len(values) >= 6:
                values[0] = self._display_source(item.source)
                # Keep the visible status intentionally short. Diagnostics are
                # available by hovering the Status cell.
                values[5] = item.status.value.upper()
                self.tree.item(row, values=values)

            tooltip_text = self._tooltip_for_item(item)
            if tooltip_text:
                self._row_tooltips[row] = tooltip_text
            row_index += 1

        # Scan errors also benefit from the relative path and hover diagnostics.
        for image, detail in self.scan_errors:
            if row_index >= len(rows):
                break
            row = rows[row_index]
            values = list(self.tree.item(row, "values"))
            if values:
                values[0] = self._display_source(image)
                self.tree.item(row, values=values)
            self._row_tooltips[row] = (
                f"ERROR\n{detail}\nSource: {self._display_source(image)}"
            )
            row_index += 1


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
