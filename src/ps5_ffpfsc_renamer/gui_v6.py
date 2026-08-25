from __future__ import annotations

from pathlib import Path

from .diagnostics import classify_reader_error, infer_metadata_from_path
from .gui_v5 import RenamerApp as RenamerAppV5
from .metadata import GameMetadata
from .theme import COLORS

PartialItem = tuple[Path, GameMetadata, str, str, str, str]


class RenamerApp(RenamerAppV5):
    """GUI with display-only metadata fallback for images MkPFS cannot parse."""

    def __init__(self) -> None:
        self.partial_items: list[PartialItem] = []
        super().__init__()

    def _scan(self) -> None:
        self.partial_items = []
        super()._scan()

    def _scan_complete(
        self,
        parsed: list[tuple[Path, GameMetadata]],
        errors: list[tuple[Path, str]],
        total: int,
        started_at: float,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        root_text = self.folder_var.get().strip()
        library_root = Path(root_text) if root_text else None

        partial: list[PartialItem] = []
        hard_errors: list[tuple[Path, str]] = []

        for image, detail in errors:
            inferred = infer_metadata_from_path(image, library_root=library_root)
            code, friendly = classify_reader_error(detail)
            if inferred is None:
                hard_errors.append((image, detail))
                continue
            partial.append(
                (
                    image,
                    inferred.metadata,
                    detail,
                    inferred.source,
                    code,
                    friendly,
                )
            )

        self.partial_items = partial
        super()._scan_complete(
            parsed,
            hard_errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )

        partial_count = len(partial)
        hard_count = len(hard_errors)
        if partial_count:
            self.progress_note_var.set(
                f"Scan complete: {cache_hits} reused from cache, {mkpfs_reads} read with MkPFS, "
                f"{partial_count} shown as PARTIAL. Partial metadata comes only from the filename/folder "
                "and is never used for automatic rename."
            )
        self.status_var.set(
            f"Scan complete — {cache_hits} cached, {mkpfs_reads} new/changed, "
            f"{partial_count} partial, {hard_count} metadata error(s)"
        )

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        super()._rebuild_output_plan(option_change=option_change)
        self.tree.tag_configure("partial", foreground=COLORS["warning"])

        # Replace raw MkPFS tracebacks in the visible table with a short label.
        # The full technical information remains available via the Status hover
        # and the right-click diagnostics action.
        error_details = {path: detail for path, detail in self.scan_errors}
        for row, source in list(self._row_sources.items()):
            if row in self._row_plan_items:
                continue
            values = list(self.tree.item(row, "values"))
            if len(values) < 6 or str(values[5]).upper() != "ERROR":
                continue
            detail = error_details.get(source, "")
            _code, friendly = classify_reader_error(detail)
            values[1] = "-"
            values[2] = "Metadata unavailable"
            values[3] = "-"
            values[4] = "-"
            values[5] = "ERROR"
            self.tree.item(row, values=values)
            self._row_tooltips[row] = (
                f"ERROR\n{friendly}\n"
                f"Source: {self._display_source(source)}\n"
                "Right-click the row and choose Run diagnostics for a read-only MkPFS inspection."
            )

        # Partial rows are intentionally not added to self.plan. They can be
        # inspected and managed from the context menu, but batch/current-plan
        # rename cannot use unverified path-derived metadata.
        for image, metadata, _detail, inference_source, _code, friendly in self.partial_items:
            row = self.tree.insert(
                "",
                "end",
                values=(
                    self._display_source(image),
                    metadata.title_id,
                    metadata.title_name or "-",
                    "-",
                    "-",
                    "PARTIAL",
                ),
                tags=("partial",),
            )
            self._row_sources[row] = image
            self._row_tooltips[row] = (
                "PARTIAL\n"
                f"{friendly}\n"
                f"Detected from: {inference_source}\n"
                f"Inferred Title ID: {metadata.title_id}\n"
                f"Inferred title: {metadata.title_name or '-'}\n"
                "These values were NOT verified inside the FFPFSC image. Automatic rename is disabled.\n"
                "Right-click the row and choose Run diagnostics for more information."
            )

        if self.partial_items:
            try:
                current_blocked = int(self.blocked_var.get())
            except (TypeError, ValueError):
                current_blocked = 0
            self.blocked_var.set(str(current_blocked + len(self.partial_items)))
            self.rename_button.configure(state="disabled")

    def _move_to_recycle_bin(self, source: Path) -> None:
        super()._move_to_recycle_bin(source)
        # If the inherited operation completed, the original path is gone.
        # Remove display-only partial state as well and refresh once more.
        if not source.exists():
            old_count = len(self.partial_items)
            self.partial_items = [item for item in self.partial_items if item[0] != source]
            if len(self.partial_items) != old_count:
                self._rebuild_output_plan(option_change=True)


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
