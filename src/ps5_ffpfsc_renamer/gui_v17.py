from __future__ import annotations

from collections import Counter

from .gui_v16 import RenamerApp as RenamerAppV16
from .library_view import human_size


class RenamerApp(RenamerAppV16):
    """v0.4 multi-selection summary for the Game Details workspace."""

    def _on_details_selection(self, _event=None) -> None:
        rows = self.tree.selection()
        if len(rows) <= 1:
            super()._on_details_selection(_event)
            return

        self._cancel_pending_details()
        self._details_record = None
        self._details_generation += 1
        records = [self._row_records[row] for row in rows if row in self._row_records]
        if not records:
            return

        self._ensure_details_visible()
        if self._details_toggle_button is not None:
            self._details_toggle_button.configure(state="normal")

        total_size = sum(record.view.size or 0 for record in records)
        known_sizes = sum(1 for record in records if record.view.size is not None)
        statuses = Counter(record.view.status for record in records)
        title_ids = {
            record.view.title_id.strip().upper()
            for record in records
            if record.view.title_id.strip() and record.view.title_id != "-"
        }
        status_text = " • ".join(f"{status} {count}" for status, count in sorted(statuses.items()))

        self._details_vars["title"].set(f"{len(records)} games selected")
        self._details_vars["title_id"].set(f"{len(title_ids)} unique Title ID(s)")
        self._details_vars["content_version"].set("-")
        self._details_vars["master_version"].set("-")
        self._details_vars["size"].set(
            f"{human_size(total_size)} across {known_sizes}/{len(records)} sized file(s)"
        )
        self._details_vars["status"].set(status_text or "-")
        self._details_vars["source"].set("In-memory selection summary — no MkPFS reads")
        self._details_vars["path"].set("Multiple files selected")
        self._reset_details_icon("MULTI\nSELECTION")
        self._set_details_json(
            "Multiple games are selected.\n\n"
            "param.json is loaded only for a single selected game so the app never starts "
            "multiple unnecessary MkPFS reads while you are batch-selecting files.\n\n"
            f"Selected: {len(records)}\n"
            f"Known total size: {human_size(total_size)}\n"
            f"Unique Title IDs: {len(title_ids)}\n"
            f"Statuses: {status_text or '-'}"
        )
        if self._details_status_var is not None:
            self._details_status_var.set(
                f"{len(records)} games • {human_size(total_size)} • no MkPFS activity"
            )


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
