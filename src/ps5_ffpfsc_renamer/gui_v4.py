from __future__ import annotations

from pathlib import Path

from .gui_v3 import RenamerApp as RenamerAppV3
from .rename_plan import PlanStatus, RenamePlanItem


class RenamerApp(RenamerAppV3):
    """GUI refinements for clearer scan results and collision diagnostics."""

    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        # Give enough room to distinguish files with the same basename that
        # live in different folders, and to explain blocked rename plans.
        self.tree.column("file", width=270, minwidth=170, anchor="w")
        self.tree.column("title", width=240, minwidth=150, anchor="w")
        self.tree.column("output", width=320, minwidth=180, anchor="w")
        self.tree.column("status", width=210, minwidth=120, anchor="w")

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
    def _display_status(item: RenamePlanItem) -> str:
        status = item.status.value.upper()
        if item.reason and item.status in {
            PlanStatus.COLLISION,
            PlanStatus.INVALID,
        }:
            return f"{status} — {item.reason}"
        return status

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        # Let the established planner update rows, counters and button state.
        super()._rebuild_output_plan(option_change=option_change)

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
                values[5] = self._display_status(item)
                self.tree.item(row, values=values)
            row_index += 1

        # Scan errors also benefit from the relative path so duplicate-looking
        # basenames are easy to distinguish.
        for image, _detail in self.scan_errors:
            if row_index >= len(rows):
                break
            row = rows[row_index]
            values = list(self.tree.item(row, "values"))
            if values:
                values[0] = self._display_source(image)
                self.tree.item(row, values=values)
            row_index += 1


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
