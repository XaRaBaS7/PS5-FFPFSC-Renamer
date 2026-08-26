from __future__ import annotations

from pathlib import Path
import tkinter as tk

from ..settings import AppSettings, load_settings, save_settings


class WorkspacePreferencesMixin:
    """Persistent library/workspace preferences extracted from gui_v9."""

    def __init__(self) -> None:
        self._prefs_ready = False
        self._save_after_id: str | None = None
        self._all_records = []
        self._row_records = {}
        self._duplicate_groups = {}
        super().__init__()

        settings = load_settings()
        self._apply_settings(settings)
        self._prefs_ready = True
        self._install_setting_watchers()
        self._rebuild_output_plan(option_change=False)

    def _apply_settings(self, settings: AppSettings) -> None:
        if settings.library_roots:
            self.library_roots = [Path(value) for value in settings.library_roots]
            self._update_root_summary()

        self.recursive_var.set(settings.recursive)
        if settings.worker in tuple(self.worker_combo.cget("values")):
            self.worker_var.set(settings.worker)

        preset_values = tuple(self.preset_combo.cget("values"))
        self.preset_var.set(
            settings.preset if settings.preset in preset_values else self.PRESET_CUSTOM
        )
        self.include_id_var.set(settings.include_title_id)
        self.include_title_var.set(settings.include_title)
        self.include_version_var.set(settings.include_version)
        self.version_format_var.set(settings.version_format)
        self.version_prefix_var.set(settings.version_prefix)

        folder_values = tuple(self.folder_mode_combo.cget("values"))
        if settings.folder_mode in folder_values:
            self.folder_mode_var.set(settings.folder_mode)

        self.component_order[:] = list(settings.component_order)
        self._render_order_editor()
        self._update_folder_help()
        self.filter_var.set(
            settings.result_filter if settings.result_filter in self.FILTERS else "ALL"
        )

        if settings.window_geometry:
            try:
                self.geometry(settings.window_geometry)
            except tk.TclError:
                pass
        self._refresh_output_preview()

    def _snapshot_settings(self) -> AppSettings:
        geometry = None
        try:
            geometry = self.geometry()
        except tk.TclError:
            pass
        return AppSettings(
            library_roots=tuple(str(root) for root in self.library_roots),
            recursive=bool(self.recursive_var.get()),
            worker=self.worker_var.get(),
            preset=self.preset_var.get(),
            include_title_id=bool(self.include_id_var.get()),
            include_title=bool(self.include_title_var.get()),
            include_version=bool(self.include_version_var.get()),
            version_format=self.version_format_var.get(),
            version_prefix=bool(self.version_prefix_var.get()),
            folder_mode=self.folder_mode_var.get(),
            component_order=tuple(self.component_order),
            result_filter=self.filter_var.get(),
            window_geometry=geometry,
        )

    def _queue_save_preferences(self, *_args) -> None:
        if not self._prefs_ready:
            return
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except tk.TclError:
                pass
        self._save_after_id = self.after(250, self._save_preferences_now)

    def _save_preferences_now(self) -> None:
        self._save_after_id = None
        if not self._prefs_ready:
            return
        try:
            save_settings(self._snapshot_settings())
        except OSError:
            pass

    def _install_setting_watchers(self) -> None:
        for variable in (
            self.recursive_var,
            self.worker_var,
            self.preset_var,
            self.include_id_var,
            self.include_title_var,
            self.include_version_var,
            self.version_format_var,
            self.version_prefix_var,
            self.folder_mode_var,
            self.filter_var,
        ):
            variable.trace_add("write", self._queue_save_preferences)
        self.bind("<Configure>", self._queue_save_preferences, add="+")
        self.protocol("WM_DELETE_WINDOW", self._close_with_settings)

    def _close_with_settings(self) -> None:
        self._save_preferences_now()
        self.destroy()

    def _update_root_summary(self) -> None:
        super()._update_root_summary()
        self._queue_save_preferences()

    def _move_component(self, index: int, direction: int) -> None:
        super()._move_component(index, direction)
        self._queue_save_preferences()

    def _apply_preset(self, event=None) -> None:
        super()._apply_preset(event)
        self._queue_save_preferences()
