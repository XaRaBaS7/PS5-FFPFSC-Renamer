from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..ffpfsc_reader import mkpfs_source_description
from ..naming import (
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    normalize_folder_handling,
)
from ..settings import AppSettings
from ..theme import COLORS


class OptionsDialogMixin:
    """Modern sidebar-based options window for desktop preferences."""

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
        window.geometry("940x680")
        window.minsize(860, 620)
        window.transient(self)
        window.grab_set()
        window.configure(bg=COLORS["bg"])

        try:
            icon = getattr(self, "_brand_icon_photo", None)
            if icon is not None:
                window.iconphoto(True, icon)
        except tk.TclError:
            pass

        outer = tk.Frame(window, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=18, pady=16)

        header = tk.Frame(outer, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 14))
        title_block = tk.Frame(header, bg=COLORS["bg"])
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_block,
            text="Options",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 22, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            title_block,
            text="Configure startup, scanning, naming and maintenance without leaving the desktop workflow.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        badge = tk.Label(
            header,
            text="LOCAL SETTINGS",
            bg=COLORS["accent_soft"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=5,
        )
        badge.pack(side="right", padx=(12, 0))

        body = tk.Frame(outer, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)

        nav = tk.Frame(
            body,
            bg=COLORS["sidebar"],
            width=228,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        nav.pack(side="left", fill="y", padx=(0, 12))
        nav.pack_propagate(False)

        tk.Label(
            nav,
            text="SETTINGS",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(15, 8))

        content_shell = tk.Frame(
            body,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        content_shell.pack(side="left", fill="both", expand=True)

        general = ttk.Frame(content_shell, style="Card.TFrame", padding=18)
        performance = ttk.Frame(content_shell, style="Card.TFrame", padding=18)
        naming = ttk.Frame(content_shell, style="Card.TFrame", padding=18)
        maintenance = ttk.Frame(content_shell, style="Card.TFrame", padding=18)
        pages = {
            "general": general,
            "performance": performance,
            "naming": naming,
            "maintenance": maintenance,
        }
        # Extension mixins add their extra controls to these pages after the
        # base dialog is created. Keeping an explicit page registry avoids
        # coupling them to a native ttk.Notebook/tab implementation.
        window._options_pages = pages  # type: ignore[attr-defined]

        auto_start = tk.BooleanVar(value=self._autoscan_on_start)
        auto_browse = tk.BooleanVar(value=self._autoscan_on_browse)
        auto_add = tk.BooleanVar(value=self._autoscan_on_add_folder)
        remember_geometry = tk.BooleanVar(value=self._remember_window_geometry)
        relative_paths = tk.BooleanVar(value=self._show_relative_paths)
        auto_prune = tk.BooleanVar(value=self._auto_prune_cache)
        recursive = tk.BooleanVar(value=bool(self.recursive_var.get()))
        worker = tk.StringVar(value=self.worker_var.get())

        preset = tk.StringVar(value=self.preset_var.get())
        folder_mode = tk.StringVar(value=self._folder_mode())
        version_format = tk.StringVar(value=self.version_format_var.get())
        version_prefix = tk.BooleanVar(value=bool(self.version_prefix_var.get()))
        include_id = tk.BooleanVar(value=bool(self.include_id_var.get()))
        include_title = tk.BooleanVar(value=bool(self.include_title_var.get()))
        include_version = tk.BooleanVar(value=bool(self.include_version_var.get()))

        def page_header(parent: ttk.Frame, title: str, note: str) -> None:
            ttk.Label(parent, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(
                parent,
                text=note,
                style="CardMuted.TLabel",
                wraplength=620,
                justify="left",
            ).pack(anchor="w", pady=(3, 14))

        def section(parent: ttk.Frame, title: str, note: str | None = None) -> ttk.Frame:
            box = ttk.Frame(parent, style="Card.TFrame")
            box.pack(fill="x", pady=(0, 14))
            ttk.Label(box, text=title, style="CardTitle.TLabel").pack(anchor="w")
            if note:
                ttk.Label(
                    box,
                    text=note,
                    style="CardMuted.TLabel",
                    wraplength=610,
                    justify="left",
                ).pack(anchor="w", pady=(2, 8))
            return box

        # ------------------------------- General
        page_header(
            general,
            "General",
            "Choose what the application does automatically and how the library is presented.",
        )
        startup_box = section(
            general,
            "Startup automation",
            "Automatic scans only read files when required; unchanged entries continue to use the metadata cache.",
        )
        for text, variable in (
            ("Scan saved folders when the app starts", auto_start),
            ("Scan immediately after Browse", auto_browse),
            ("Scan immediately after Add folder", auto_add),
        ):
            ttk.Checkbutton(startup_box, text=text, variable=variable).pack(anchor="w", pady=3)

        display_box = section(general, "Window & result display")
        for text, variable in (
            ("Remember window size and position", remember_geometry),
            ("Show compact relative paths in the results table", relative_paths),
        ):
            ttk.Checkbutton(display_box, text=text, variable=variable).pack(anchor="w", pady=3)

        ttk.Label(
            general,
            text="Manual scan is always available with Scan now or F5.",
            style="CardInfo.TLabel",
            wraplength=610,
        ).pack(anchor="w")

        # ------------------------------- Performance
        page_header(
            performance,
            "Scan & performance",
            "Keep HDD libraries conservative; increase parallelism only when the storage can sustain it.",
        )
        scan_box = section(
            performance,
            "Scan strategy",
            "Metadata analysis is storage-bound. One worker remains the safest profile for mechanical disks.",
        )
        ttk.Checkbutton(
            scan_box,
            text="Include subfolders",
            variable=recursive,
        ).pack(anchor="w", pady=(0, 8))

        worker_row = ttk.Frame(scan_box, style="Card.TFrame")
        worker_row.pack(fill="x")
        ttk.Label(worker_row, text="Workers", style="CardMuted.TLabel").pack(side="left")
        ttk.Combobox(
            worker_row,
            textvariable=worker,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=21,
            style="Performance.TCombobox",
        ).pack(side="left", padx=(10, 0))

        cache_box = section(
            performance,
            "Cache behavior",
            "Cache pruning is skipped whenever a configured USB/NAS root is unavailable, so disconnected libraries are not treated as deleted.",
        )
        ttk.Checkbutton(
            cache_box,
            text="Prune cache entries for files confirmed missing at startup",
            variable=auto_prune,
        ).pack(anchor="w", pady=3)
        ttk.Label(
            performance,
            text=(
                "Unchanged VERIFIED and unchanged PARTIAL/ERROR records stay cached, reducing repeated MkPFS reads."
            ),
            style="CardInfo.TLabel",
            wraplength=610,
        ).pack(anchor="w")

        # ------------------------------- Naming
        page_header(
            naming,
            "Naming",
            "Set filename defaults and choose the final library organization. These settings update the main Filename Builder too.",
        )
        filename_box = section(naming, "Filename defaults")
        filename_grid = ttk.Frame(filename_box, style="Card.TFrame")
        filename_grid.pack(fill="x")
        filename_grid.columnconfigure(0, weight=1)
        filename_grid.columnconfigure(1, weight=1)

        ttk.Label(filename_grid, text="Preset", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            filename_grid,
            textvariable=preset,
            values=tuple(self.preset_combo.cget("values")),
            state="readonly",
            style="Performance.TCombobox",
            width=28,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(3, 10))

        ttk.Label(filename_grid, text="Version format", style="CardMuted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Combobox(
            filename_grid,
            textvariable=version_format,
            values=(self.VERSION_COMPACT, self.VERSION_ORIGINAL),
            state="readonly",
            style="Performance.TCombobox",
            width=28,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(3, 10))

        component_row = ttk.Frame(filename_box, style="Card.TFrame")
        component_row.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(component_row, text="PPSA / Title ID", variable=include_id).pack(side="left")
        ttk.Checkbutton(component_row, text="Game title", variable=include_title).pack(
            side="left", padx=(16, 0)
        )
        ttk.Checkbutton(component_row, text="Version", variable=include_version).pack(
            side="left", padx=(16, 0)
        )
        ttk.Checkbutton(component_row, text="Prefix version with 'v'", variable=version_prefix).pack(
            side="left", padx=(16, 0)
        )

        organization_box = section(
            naming,
            "Library organization",
            "Choose the result you want on disk. The selected library root itself is never renamed.",
        )
        organization_cards: dict[str, dict[str, tk.Widget]] = {}

        def refresh_organization_cards() -> None:
            selected = normalize_folder_handling(folder_mode.get())
            for mode, widgets in organization_cards.items():
                active = mode == selected
                background = COLORS["accent_soft"] if active else COLORS["surface"]
                border = COLORS["accent"] if active else COLORS["border"]
                widgets["frame"].configure(bg=background, highlightbackground=border)
                widgets["indicator"].configure(
                    text="●" if active else "○",
                    bg=background,
                    fg=COLORS["accent_hover"] if active else COLORS["muted"],
                )
                widgets["title"].configure(bg=background)
                widgets["description"].configure(
                    bg=background,
                    fg=COLORS["text_soft"] if active else COLORS["muted"],
                )

        def select_organization(mode: str) -> None:
            folder_mode.set(normalize_folder_handling(mode))
            refresh_organization_cards()

        organization_defs = (
            (
                FOLDER_ONE_PER_GAME,
                self.FOLDER_ONE_PER_GAME_LABEL,
                "Each .ffpfsc ends in its own named folder directly under the library root.",
            ),
            (
                FOLDER_ROOT_FLAT,
                self.FOLDER_ROOT_FLAT_LABEL,
                "Every .ffpfsc ends directly in the library root, with no per-game folders.",
            ),
            (
                FOLDER_KEEP_STRUCTURE,
                self.FOLDER_KEEP_STRUCTURE_LABEL,
                "Rename files where they are now; do not move, create or rename folders.",
            ),
        )
        for mode, title, description in organization_defs:
            frame = tk.Frame(
                organization_box,
                bg=COLORS["surface"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                cursor="hand2",
            )
            frame.pack(fill="x", pady=(0, 6))
            indicator = tk.Label(
                frame,
                text="○",
                bg=COLORS["surface"],
                fg=COLORS["muted"],
                font=("Segoe UI", 11, "bold"),
                cursor="hand2",
            )
            indicator.pack(side="left", padx=(10, 8), pady=8)
            text_box = tk.Frame(frame, bg=COLORS["surface"], cursor="hand2")
            text_box.pack(side="left", fill="x", expand=True, pady=7)
            title_label = tk.Label(
                text_box,
                text=title,
                bg=COLORS["surface"],
                fg=COLORS["text"],
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                cursor="hand2",
            )
            title_label.pack(fill="x")
            description_label = tk.Label(
                text_box,
                text=description,
                bg=COLORS["surface"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
                cursor="hand2",
            )
            description_label.pack(fill="x", pady=(1, 0))
            widgets = (frame, indicator, text_box, title_label, description_label)
            for widget in widgets:
                widget.bind(
                    "<Button-1>",
                    lambda _event, selected=mode: select_organization(selected),
                )
            organization_cards[mode] = {
                "frame": frame,
                "indicator": indicator,
                "title": title_label,
                "description": description_label,
            }
        refresh_organization_cards()

        # ------------------------------- Maintenance
        page_header(
            maintenance,
            "Cache & engine",
            "Inspect local metadata storage and the MkPFS source used for uncached files.",
        )
        metadata_box = section(
            maintenance,
            "Metadata cache",
            "The cache stores parsed metadata and failure records only; it does not copy FFPFSC payload data.",
        )
        try:
            stats = self.cache.stats()
            cache_text = (
                f"Verified metadata: {stats.entries}   •   Cached failures: {stats.failed_entries}   •   "
                f"Database: {stats.database_bytes / (1024 * 1024):.2f} MiB"
            )
        except Exception:
            cache_text = "Cache statistics unavailable"
        ttk.Label(metadata_box, text=cache_text, style="CardInfo.TLabel").pack(anchor="w")

        cache_buttons = ttk.Frame(metadata_box, style="Card.TFrame")
        cache_buttons.pack(fill="x", pady=(10, 0))
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

        engine_box = section(
            maintenance,
            "MkPFS engine",
            "The bundled release helper uses the low-memory metadata path when available.",
        )
        engine_status = tk.Frame(
            engine_box,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        engine_status.pack(fill="x", pady=(0, 10))
        tk.Label(
            engine_status,
            text="ACTIVE SOURCE",
            bg=COLORS["surface"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 7, "bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(7, 1))
        tk.Label(
            engine_status,
            text=mkpfs_source_description(),
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=590,
        ).pack(fill="x", padx=10, pady=(0, 7))
        ttk.Button(
            engine_box,
            text="Configure MkPFS engine...",
            image=self._icon("engine", 16),
            compound="left",
            command=lambda: (window.grab_release(), self._show_mkpfs_settings()),
        ).pack(anchor="w")

        nav_items: dict[str, dict[str, tk.Widget]] = {}
        nav_definitions = (
            ("general", "General", "Startup & display"),
            ("performance", "Scan & performance", "Workers & cache behavior"),
            ("naming", "Naming", "Filename & library layout"),
            ("maintenance", "Cache & engine", "Maintenance & MkPFS"),
        )
        active_page = tk.StringVar(value="general")

        def show_page(key: str) -> None:
            if key not in pages:
                return
            active_page.set(key)
            for page_key, page in pages.items():
                if page_key == key:
                    page.pack(fill="both", expand=True)
                else:
                    page.pack_forget()
            for item_key, widgets in nav_items.items():
                selected = item_key == key
                background = COLORS["accent_soft"] if selected else COLORS["sidebar"]
                widgets["frame"].configure(
                    bg=background,
                    highlightbackground=COLORS["accent"] if selected else COLORS["sidebar"],
                )
                widgets["bar"].configure(
                    bg=COLORS["accent"] if selected else background
                )
                widgets["title"].configure(
                    bg=background,
                    fg=COLORS["accent_hover"] if selected else COLORS["text_soft"],
                )
                widgets["note"].configure(bg=background)

        for key, title, note in nav_definitions:
            item = tk.Frame(
                nav,
                bg=COLORS["sidebar"],
                highlightthickness=1,
                highlightbackground=COLORS["sidebar"],
                cursor="hand2",
            )
            item.pack(fill="x", padx=8, pady=2)
            bar = tk.Frame(item, bg=COLORS["sidebar"], width=3)
            bar.pack(side="left", fill="y")
            text = tk.Frame(item, bg=COLORS["sidebar"], cursor="hand2")
            text.pack(side="left", fill="both", expand=True, padx=10, pady=8)
            title_label = tk.Label(
                text,
                text=title,
                bg=COLORS["sidebar"],
                fg=COLORS["text_soft"],
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                cursor="hand2",
            )
            title_label.pack(fill="x")
            note_label = tk.Label(
                text,
                text=note,
                bg=COLORS["sidebar"],
                fg=COLORS["muted_dark"],
                font=("Segoe UI", 8),
                anchor="w",
                cursor="hand2",
            )
            note_label.pack(fill="x", pady=(1, 0))
            for widget in (item, bar, text, title_label, note_label):
                widget.bind("<Button-1>", lambda _event, target=key: show_page(target))
            nav_items[key] = {
                "frame": item,
                "bar": bar,
                "title": title_label,
                "note": note_label,
            }

        tk.Label(
            nav,
            text="Changes are saved only when you click Save.",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8),
            wraplength=190,
            justify="left",
            anchor="w",
        ).pack(side="bottom", fill="x", padx=14, pady=14)

        show_page("general")

        buttons = tk.Frame(outer, bg=COLORS["bg"])
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
            select_organization(defaults.folder_mode)
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
            self._set_folder_mode(folder_mode.get())
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

        ttk.Button(
            buttons,
            text="Restore defaults",
            style="Secondary.TButton",
            command=restore_defaults,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Cancel",
            style="Secondary.TButton",
            command=window.destroy,
        ).pack(side="right")
        ttk.Button(
            buttons,
            text="Save changes",
            image=self._icon("options", 16, COLORS["accent_hover"]),
            compound="left",
            style="Primary.TButton",
            command=apply,
        ).pack(side="right", padx=(0, 8))

        window.bind("<Escape>", lambda _event: window.destroy())
