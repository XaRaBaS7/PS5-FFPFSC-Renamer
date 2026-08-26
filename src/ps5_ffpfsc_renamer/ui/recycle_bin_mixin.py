from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from send2trash import send2trash

from ..library_view import human_size, safe_file_size
from ..workspace_models import LibraryRecord


class RecycleBinMixin:
    """Existing confirmed UI action that moves selected files to the OS Recycle Bin."""

    def _delete_records(self, records: list[LibraryRecord]) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for record in records:
            path = record.view.source.resolve()
            key = str(path).casefold()
            if key not in seen and path.exists():
                seen.add(key)
                unique.append(path)
        if not unique:
            return
        total_size = sum((safe_file_size(path) or 0) for path in unique)
        if not messagebox.askyesno(
            "Move to Recycle Bin",
            f"Move {len(unique)} selected file(s) ({human_size(total_size)}) to the Windows Recycle Bin?\n\n"
            "This action does not permanently delete them.",
            icon="warning",
            parent=self,
        ):
            return

        removed: list[Path] = []
        errors: list[str] = []
        for path in unique:
            try:
                send2trash(str(path))
                removed.append(path)
                try:
                    self.cache.remove(path)
                except Exception:
                    pass
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        removed_keys = {str(path).casefold() for path in removed}
        self.parsed_items = [
            (path, metadata)
            for path, metadata in self.parsed_items
            if str(path.resolve()).casefold() not in removed_keys
        ]
        self.scan_errors = [
            (path, detail)
            for path, detail in self.scan_errors
            if str(path.resolve()).casefold() not in removed_keys
        ]
        self.partial_items = [
            item
            for item in self.partial_items
            if str(item[0].resolve()).casefold() not in removed_keys
        ]
        self.files_var.set(str(max(0, int(self.files_var.get() or "0") - len(removed))))
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Moved {len(removed)} file(s) to Recycle Bin")
        if errors:
            messagebox.showwarning(
                "Recycle Bin",
                "Some files could not be moved:\n\n" + "\n".join(errors[:8]),
                parent=self,
            )
