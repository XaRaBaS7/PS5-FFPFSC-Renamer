from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

from send2trash import send2trash

from .ffpfsc_reader import MetadataReadError, read_metadata
from .gui_v4 import RenamerApp as RenamerAppV4
from .rename_plan import PlanStatus, RenamePlanItem
from .renamer import apply_rename_plan
from .theme import COLORS


class RenamerApp(RenamerAppV4):
    """Desktop UI with a Windows-style right-click file action menu."""

    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        self._row_plan_items: dict[str, RenamePlanItem] = {}
        self._row_sources: dict[str, Path] = {}
        self.tree.bind("<Button-3>", self._show_context_menu, add="+")

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        super()._rebuild_output_plan(option_change=option_change)
        self._row_plan_items.clear()
        self._row_sources.clear()

        rows = list(self.tree.get_children())
        index = 0
        for item in self.plan:
            if index >= len(rows):
                break
            row = rows[index]
            self._row_plan_items[row] = item
            self._row_sources[row] = item.source
            index += 1

        for image, _detail in self.scan_errors:
            if index >= len(rows):
                break
            self._row_sources[rows[index]] = image
            index += 1

    # ------------------------------------------------------ context menu
    def _show_context_menu(self, event) -> str:
        row = self.tree.identify_row(event.y)
        if not row:
            return "break"

        self._hide_tree_tooltip()
        self.tree.selection_set(row)
        self.tree.focus(row)

        source = self._row_sources.get(row)
        item = self._row_plan_items.get(row)
        if source is None:
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

        if item is not None:
            menu.add_command(
                label="Rename using current plan",
                command=lambda selected=item: self._rename_selected_plan(selected),
                state="normal" if item.status is PlanStatus.READY else "disabled",
            )
            menu.add_command(
                label="Rename file manually...",
                command=lambda path=source: self._manual_rename(path),
            )
            menu.add_separator()

        menu.add_command(
            label="Show in Explorer",
            command=lambda path=source: self._show_in_explorer(path),
        )
        menu.add_command(
            label="Open folder",
            command=lambda path=source: self._open_folder(path),
        )
        menu.add_separator()
        menu.add_command(
            label="Copy full path",
            command=lambda path=source: self._copy_text(str(path)),
        )

        if item is not None:
            menu.add_command(
                label="Copy Title ID / PPSA",
                command=lambda value=item.metadata.title_id: self._copy_text(value),
            )
            menu.add_command(
                label="Show details",
                command=lambda selected=item: self._show_details(selected),
            )
            menu.add_command(
                label="Analyze again",
                command=lambda selected=item: self._reanalyze_selected(selected),
            )

            if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}:
                menu.add_separator()
                menu.add_command(
                    label="Why blocked?",
                    command=lambda selected=item: self._show_block_reason(selected),
                )

        menu.add_separator()
        menu.add_command(
            label="Move to Recycle Bin...",
            command=lambda path=source: self._move_to_recycle_bin(path),
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    # ----------------------------------------------------------- actions
    @staticmethod
    def _show_in_explorer(path: Path) -> None:
        path = path.resolve()
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])

    @staticmethod
    def _open_folder(path: Path) -> None:
        folder = path.resolve().parent
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.status_var.set("Copied to clipboard")

    def _show_details(self, item: RenamePlanItem) -> None:
        metadata = item.metadata
        version = metadata.content_version or metadata.master_version or "-"
        text = (
            f"File: {item.source.name}\n"
            f"Path: {item.source}\n\n"
            f"Title ID: {metadata.title_id}\n"
            f"Title: {metadata.title_name or '-'}\n"
            f"Version: {version}\n\n"
            f"Proposed output: {item.destination}\n"
            f"Status: {item.status.value.upper()}"
        )
        if item.reason:
            text += f"\nReason: {self._friendly_reason(item.reason)}"
        messagebox.showinfo("FFPFSC details", text, parent=self)

    def _show_block_reason(self, item: RenamePlanItem) -> None:
        text = self._tooltip_for_item(item) or "This file is not blocked."
        messagebox.showinfo("Why blocked?", text, parent=self)

    def _rename_selected_plan(self, item: RenamePlanItem) -> None:
        if item.status is not PlanStatus.READY:
            return
        if not messagebox.askyesno(
            "Rename selected file",
            f"Apply the current plan only to this file?\n\n"
            f"From:\n{item.source}\n\nTo:\n{item.destination}",
            parent=self,
        ):
            return

        try:
            completed = apply_rename_plan([item])
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return

        if not completed:
            return
        old_path, new_path = completed[0]
        try:
            self.cache.update_path_after_rename(old_path, new_path)
        except Exception:
            pass

        self.parsed_items = [
            (new_path if path == old_path else path, metadata)
            for path, metadata in self.parsed_items
        ]
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Renamed: {new_path.name}")

    def _manual_rename(self, source: Path) -> None:
        if not source.exists():
            messagebox.showerror("Rename", "The selected file no longer exists.", parent=self)
            return

        entered = simpledialog.askstring(
            "Rename file manually",
            "New filename:",
            initialvalue=source.name,
            parent=self,
        )
        if entered is None:
            return

        name = entered.strip()
        if not name:
            return
        if not name.lower().endswith(".ffpfsc"):
            name += ".ffpfsc"
        if Path(name).name != name or any(char in name for char in '<>:"/\\|?*'):
            messagebox.showerror(
                "Invalid filename",
                "Use only a filename, without path characters or Windows-invalid characters.",
                parent=self,
            )
            return

        destination = source.with_name(name)
        if destination == source:
            return
        if destination.exists():
            messagebox.showerror("Rename", "A file with that name already exists.", parent=self)
            return

        try:
            source.rename(destination)
        except OSError as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return

        try:
            self.cache.update_path_after_rename(source, destination)
        except Exception:
            pass
        self.parsed_items = [
            (destination if path == source else path, metadata)
            for path, metadata in self.parsed_items
        ]
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Renamed manually: {destination.name}")

    def _reanalyze_selected(self, item: RenamePlanItem) -> None:
        if self._scan_active:
            messagebox.showinfo(
                "Analyze again",
                "Wait for the current library scan to finish first.",
                parent=self,
            )
            return

        source = item.source
        self.status_var.set(f"Analyzing again: {source.name}...")

        def worker() -> None:
            try:
                metadata = read_metadata(source, cache=self.cache, use_cache=False)
                try:
                    self.cache.store(source, metadata)
                except Exception:
                    pass
            except (MetadataReadError, OSError) as exc:
                self.after(
                    0,
                    lambda error=str(exc): messagebox.showerror(
                        "Analyze again", error, parent=self
                    ),
                )
                return

            def done() -> None:
                self.parsed_items = [
                    (path, metadata if path == source else old_metadata)
                    for path, old_metadata in self.parsed_items
                ]
                self.cache_entries_var.set(str(self.cache.entry_count()))
                self._rebuild_output_plan(option_change=True)
                self.status_var.set(f"Re-analyzed with MkPFS: {source.name}")

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _move_to_recycle_bin(self, source: Path) -> None:
        if not source.exists():
            messagebox.showerror("Recycle Bin", "The selected file no longer exists.", parent=self)
            return

        if not messagebox.askyesno(
            "Move to Recycle Bin",
            f"Move this file to the Windows Recycle Bin?\n\n{source}\n\n"
            "It will not be permanently deleted by this action.",
            icon="warning",
            parent=self,
        ):
            return

        try:
            send2trash(str(source))
        except Exception as exc:
            messagebox.showerror("Recycle Bin", str(exc), parent=self)
            return

        self.parsed_items = [
            (path, metadata)
            for path, metadata in self.parsed_items
            if path != source
        ]
        self.scan_errors = [
            (path, detail) for path, detail in self.scan_errors if path != source
        ]
        self.files_var.set(str(max(0, int(self.files_var.get() or "0") - 1)))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Moved to Recycle Bin: {source.name}")


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
