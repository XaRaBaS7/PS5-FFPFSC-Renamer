from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..ffpfsc_reader import mkpfs_source_description
from ..settings import AppSettings
from ..theme import COLORS


class OptionsDialogMixin:
    """Central General/Performance/Naming/Cache & Engine options window."""

    def _show_options(self) -> None:
        if self._scan_active:
            messagebox.showinfo(
                "Options",
                "Wait for the current scan to finish before changing scan options.",
                parent=self,
            )
            return

        window = tk.Toplevel(self)
        window.title("PS5 FFPFSC Renamer — Options")
        window.geometry("790x600")
        window.minsize(700, 520)
        window.transient(self)
        window.grab_set()
        window.configure(bg=COLORS["bg"])

        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Options", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Changes are saved to your local settings file.",
            style="Subtitle.TLabel",
        ).pack(side="right")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        general = ttk.Frame(notebook, padding=16)
        performance = ttk.Frame(notebook, padding=16)
        naming = ttk.Frame(notebook, padding=16)
        maintenance = ttk.Frame(notebook, padding=16)
        notebook.add(general, text="General")
        notebook.add(performance, text="Scan & Performance")
        notebook.add(naming, text="Naming")
        notebook.add(maintenance, text="Cache & Engine")

        auto_start = tk.BooleanVar(value=self._autoscan_on_start)
        auto_browse = tk.BooleanVar(value=self._autoscan_on_browse)
        auto_add = tk.BooleanVar(value=self._autoscan_on_add_folder)
        remember_geometry = tk.BooleanVar(value=self._remember_window_geometry)
        relative_paths = tk.BooleanVar(value=self._show_relative_paths)
        auto_prune = tk.BooleanVar(value=self._auto_prune_cache)
        recursive = tk.BooleanVar(value=bool(self.recursive_var.get()))
        worker = tk.StringVar(value=self.worker_var.get())

        preset = tk.StringVar(value=self.preset_var.get())
        folder_mode = tk.StringVar(value=self.folder_mode_var.get())
        version_format = tk.StringVar(value=self.version_format_var.get())
        version_prefix = tk.BooleanVar(value=bool(self.version_prefix_var.get()))
        include_id = tk.BooleanVar(value=bool(self.include_id_var.get()))
        include_title = tk.BooleanVar(value=bool(self.include_title_var.get()))
        include_version = tk.BooleanVar(value=bool(self.include_version_var.get()))

        def section(parent: ttk.Frame, title: str, note: str) -> None:
            ttk.Label(parent, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(parent, text=note, style="CardMuted.TLabel", wraplength=700).pack(
                anchor="w", pady=(2, 10)
            )

        section(
            general,
            "Startup & library behavior",
            "Control when scans start automatically and how paths are displayed.",
        )
        for text, variable in (
            ("Automatically scan saved folders when the app starts", auto_start),
            ("Automatically scan after Browse", auto_browse),
            ("Automatically scan after Add folder", auto_add),
            ("Remember window size and position", remember_geometry),
            ("Show compact relative paths in the results table", relative_paths),
        ):
            ttk.Checkbutton(general, text=text, variable=variable).pack(anchor="w", pady=4)

        ttk.Separator(general).pack(fill="x", pady=14)
        ttk.Label(
            general,
            text="Manual scan is always available with Scan now or F5, regardless of these settings.",
            style="CardInfo.TLabel",
            wraplength=690,
        ).pack(anchor="w")

        section(
            performance,
            "Scan strategy",
            "The metadata reader is primarily storage-bound. Use conservative parallelism on HDDs and more workers only on SSD/NVMe storage.",
        )
        ttk.Checkbutton(
            performance,
            text="Include subfolders",
            variable=recursive,
        ).pack(anchor="w", pady=(0, 10))
        worker_row = ttk.Frame(performance)
        worker_row.pack(fill="x", pady=(0, 10))
        ttk.Label(worker_row, text="Workers", style="CardMuted.TLabel").pack(side="left")
        ttk.Combobox(
            worker_row,
            textvariable=worker,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=20,
            style="Performance.TCombobox",
        ).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(
            performance,
            text="Prune cache entries for missing files when the app starts",
            variable=auto_prune,
        ).pack(anchor="w", pady=4)
        ttk.Label(
            performance,
            text="Unchanged verified files and unchanged PARTIAL/ERROR files use the local cache, so repeat scans avoid unnecessary MkPFS reads.",
            style="CardInfo.TLabel",
            wraplength=690,
        ).pack(anchor="w", pady=(14, 0))

        section(
            naming,
            "Default filename behavior",
            "These are the same settings as Filename Builder. You can still adjust component order directly in the main window.",
        )
        grid = ttk.Frame(naming)
        grid.pack(fill="x")
        for col in range(2):
            grid.columnconfigure(col, weight=1)

        ttk.Label(grid, text="Preset", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grid,
            textvariable=preset,
            values=(self.PRESET_PPSA, self.PRESET_TITLE, self.PRESET_FULL, self.PRESET_CUSTOM),
            state="readonly",
            width=28,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(3, 12))

        ttk.Label(grid, text="Folder handling", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            grid,
            textvariable=folder_mode,
            values=tuple(self.folder_mode_combo.cget("values")),
            state="readonly",
            width=28,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(3, 12))

        ttk.Label(grid, text="Version format", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            grid,
            textvariable=version_format,
            values=(self.VERSION_COMPACT, self.VERSION_ORIGINAL),
            state="readonly",
            width=28,
        ).grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(3, 12))
        ttk.Checkbutton(
            grid,
            text="Prefix version with 'v'",
            variable=version_prefix,
        ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(3, 12))

        components = ttk.LabelFrame(naming, text="Filename components", padding=10)
        components.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(components, text="PPSA / Title ID", variable=include_id).pack(side="left")
        ttk.Checkbutton(components, text="Game title", variable=include_title).pack(
            side="left", padx=(18, 0)
        )
        ttk.Checkbutton(components, text="Version", variable=include_version).pack(
            side="left", padx=(18, 0)
        )

        section(
            maintenance,
            "Cache & MkPFS",
            "Maintenance actions are kept here so the main library screen stays focused on results.",
        )
        try:
            stats = self.cache.stats()
            cache_text = (
                f"Verified metadata: {stats.entries}   •   Cached failures: {stats.failed_entries}   •   "
                f"Database: {stats.database_bytes / (1024 * 1024):.2f} MiB"
            )
        except Exception:
            cache_text = "Cache statistics unavailable"
        ttk.Label(maintenance, text=cache_text, style="CardInfo.TLabel").pack(anchor="w")

        cache_buttons = ttk.Frame(maintenance)
        cache_buttons.pack(fill="x", pady=(12, 18))
        ttk.Button(
            cache_buttons,
            text="Cache Manager...",
            image=self._icon("cache", 16),
            compound="left",
            command=lambda: (window.grab_release(), self._show_cache_manager()),
        ).pack(side="left")
        ttk.Button(
            cache_buttons,
            text="Open app data",
            command=self._open_app_data_folder,
        ).pack(side="left", padx=(8, 0))

        ttk.Separator(maintenance).pack(fill="x", pady=(0, 14))
        ttk.Label(maintenance, text="MkPFS engine", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            maintenance,
            text=mkpfs_source_description(),
            style="CardInfo.TLabel",
            wraplength=690,
        ).pack(anchor="w", pady=(4, 10))
        ttk.Button(
            maintenance,
            text="Configure MkPFS engine...",
            image=self._icon("engine", 16),
            compound="left",
            command=lambda: (window.grab_release(), self._show_mkpfs_settings()),
        ).pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))

        def restore_defaults() -> None:
            defaults = AppSettings()
            auto_start.set(defaults.autoscan_on_start)
            auto_browse.set(defaults.autoscan_on_browse)
            auto_add.set(defaults.autoscan_on_add_folder)
            remember_geometry.set(defaults.remember_window_geometry)
            relative_paths.set(defaults.show_relative_paths)
            auto_prune.set(defaults.auto_prune_cache)
            recursive.set(defaults.recursive)
            worker.set(defaults.worker)
            preset.set(defaults.preset)
            folder_mode.set(defaults.folder_mode)
            version_format.set(defaults.version_format)
            version_prefix.set(defaults.version_prefix)
            include_id.set(defaults.include_title_id)
            include_title.set(defaults.include_title)
            include_version.set(defaults.include_version)

        def apply(close: bool = True) -> None:
            previous_auto_prune = self._auto_prune_cache
            self._autoscan_on_start = bool(auto_start.get())
            self._autoscan_on_browse = bool(auto_browse.get())
            self._autoscan_on_add_folder = bool(auto_add.get())
            self._remember_window_geometry = bool(remember_geometry.get())
            self._show_relative_paths = bool(relative_paths.get())
            self._auto_prune_cache = bool(auto_prune.get())
            self.recursive_var.set(bool(recursive.get()))
            self.worker_var.set(worker.get())

            self.preset_var.set(preset.get())
            self.include_id_var.set(bool(include_id.get()))
            self.include_title_var.set(bool(include_title.get()))
            self.include_version_var.set(bool(include_version.get()))
            self.version_format_var.set(version_format.get())
            self.version_prefix_var.set(bool(version_prefix.get()))
            self.folder_mode_var.set(folder_mode.get())
            self._update_folder_help()
            self._refresh_output_preview()
            self._rebuild_output_plan(option_change=True)
            self._render_records()
            self._queue_save_preferences()
            if self._auto_prune_cache and not previous_auto_prune:
                self._auto_prune_started = False
                self._auto_prune_probe_pending = False
                self.after(40, self._schedule_auto_prune_cache)
            self.status_var.set("Options saved")
            if close:
                window.destroy()

        ttk.Button(buttons, text="Restore defaults", command=restore_defaults).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Save",
            image=self._icon("options", 16, COLORS["accent_hover"]),
            compound="left",
            style="Primary.TButton",
            command=apply,
        ).pack(side="right", padx=(0, 8))