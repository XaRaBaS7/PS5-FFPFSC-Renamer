from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..settings import AppSettings, save_settings
from ..settings_backup import (
    SettingsBackupError,
    export_settings_backup,
    load_settings_backup,
)


class SettingsBackupMixin:
    """Portable configuration-only settings backup and restore actions."""

    @staticmethod
    def _find_options_notebook(widget: tk.Misc) -> ttk.Notebook | None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook):
                return child
            nested = SettingsBackupMixin._find_options_notebook(child)
            if nested is not None:
                return nested
        return None

    def _show_options(self) -> None:
        before = set(self.winfo_children())
        super()._show_options()
        created = [
            child
            for child in self.winfo_children()
            if child not in before and isinstance(child, tk.Toplevel)
        ]
        if not created:
            return

        window = created[-1]
        notebook = self._find_options_notebook(window)
        if notebook is None:
            return
        tabs = notebook.tabs()
        if not tabs:
            return

        try:
            general = notebook.nametowidget(tabs[0])
        except KeyError:
            return

        ttk.Separator(general).pack(fill="x", pady=(16, 14))
        ttk.Label(
            general,
            text="Settings backup",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            general,
            text=(
                "Export or restore application configuration only. "
                "Metadata caches, Game Details cache, operation history, activity log "
                "and FFPFSC files are not included."
            ),
            style="CardMuted.TLabel",
            wraplength=690,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        actions = ttk.Frame(general)
        actions.pack(fill="x")

        ttk.Button(
            actions,
            text="Export settings...",
            command=lambda: self._export_settings_backup(parent=window),
        ).pack(side="left")

        def import_settings() -> None:
            if self._import_settings_backup(parent=window):
                window.destroy()

        ttk.Button(
            actions,
            text="Import settings...",
            command=import_settings,
        ).pack(side="left", padx=(8, 0))

    def _export_settings_backup(self, *, parent: tk.Misc | None = None) -> bool:
        dialog_parent = parent or self
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        selected = filedialog.asksaveasfilename(
            title="Export settings",
            parent=dialog_parent,
            defaultextension=".json",
            initialfile=f"PS5-FFPFSC-Renamer-settings-{stamp}.json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not selected:
            return False

        destination = Path(selected)
        try:
            export_settings_backup(self._snapshot_settings(), destination)
        except (OSError, SettingsBackupError) as exc:
            messagebox.showerror("Settings backup", str(exc), parent=dialog_parent)
            return False

        self.status_var.set(f"Settings backup exported: {destination.name}")
        self._log("OK", f"Settings backup exported: {destination}")
        return True

    def _apply_restored_runtime_settings(self, settings: AppSettings) -> None:
        # WorkspacePreferences intentionally preserves roots when a normal
        # settings object has no roots. Restore semantics replace the complete
        # configuration, so an empty backup root list must clear current roots.
        self.library_roots = [Path(value) for value in settings.library_roots]
        self._apply_settings(settings)

        self._update_root_summary()
        self._update_folder_help()
        self._refresh_output_preview()
        self._refresh_sort_headings()
        if hasattr(self, "_apply_tree_sort"):
            self._apply_tree_sort()
        if hasattr(self, "_refresh_watch_ui"):
            self._refresh_watch_ui()
        if hasattr(self, "_restart_library_watch"):
            self._restart_library_watch()

        self._rebuild_output_plan(option_change=True)
        if hasattr(self, "_render_records"):
            self._render_records()

    def _cancel_pending_settings_save(self) -> None:
        after_id = getattr(self, "_save_after_id", None)
        if after_id is None:
            return
        try:
            self.after_cancel(after_id)
        except tk.TclError:
            pass
        self._save_after_id = None

    def _import_settings_backup(self, *, parent: tk.Misc | None = None) -> bool:
        dialog_parent = parent or self
        selected = filedialog.askopenfilename(
            title="Import settings",
            parent=dialog_parent,
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not selected:
            return False

        source = Path(selected)
        try:
            settings = load_settings_backup(source)
        except SettingsBackupError as exc:
            messagebox.showerror("Settings backup", str(exc), parent=dialog_parent)
            return False

        if not messagebox.askyesno(
            "Import settings",
            (
                "Replace the current application settings with the selected backup?\n\n"
                "Metadata caches, Game Details cache, operation history, activity log "
                "and FFPFSC files are not modified."
            ),
            parent=dialog_parent,
        ):
            return False

        previous = self._snapshot_settings()
        try:
            self._cancel_pending_settings_save()
            self._apply_restored_runtime_settings(settings)
            save_settings(self._snapshot_settings())
            self._cancel_pending_settings_save()
        except Exception as exc:
            try:
                self._apply_restored_runtime_settings(previous)
                self._cancel_pending_settings_save()
            except Exception:
                pass
            messagebox.showerror(
                "Settings backup",
                f"Settings could not be restored: {exc}",
                parent=dialog_parent,
            )
            return False

        self.status_var.set(
            f"Settings backup imported: {source.name} — press Scan now or F5 to refresh library data"
        )
        self._log("OK", f"Settings backup imported: {source}")
        return True
