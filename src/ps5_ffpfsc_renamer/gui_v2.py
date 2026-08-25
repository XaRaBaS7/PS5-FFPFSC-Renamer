from __future__ import annotations

import threading
import time
import tkinter as tk
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .cache import MetadataCache
from .ffpfsc_reader import (
    MetadataReadCancelled,
    MetadataReadError,
    mkpfs_available,
    read_metadata,
)
from .metadata import GameMetadata
from .naming import NamingOptions, build_output_stem, example_output
from .rename_plan import PlanStatus, RenamePlanItem, build_rename_plan
from .renamer import apply_rename_plan
from .scanner import scan_ffpfsc
from .theme import COLORS, apply_theme


class RenamerApp(tk.Tk):
    PRESET_PPSA = "PPSA only (compatible)"
    PRESET_TITLE = "PPSA + Title"
    PRESET_FULL = "PPSA + Title + Version"
    PRESET_CUSTOM = "Custom"

    VERSION_COMPACT = "Compact (1.0 / 2.5)"
    VERSION_ORIGINAL = "Original (01.000.000)"

    def __init__(self) -> None:
        super().__init__()
        self.title("PS5 FFPFSC Renamer")
        self.geometry("1380x900")
        self.minsize(1120, 760)
        apply_theme(self)

        self.cache = MetadataCache()
        self.cancel_event = threading.Event()
        self._scan_active = False

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.worker_var = tk.StringVar(value="1 (HDD / safest)")

        self.files_var = tk.StringVar(value="0")
        self.cached_var = tk.StringVar(value="0")
        self.ready_var = tk.StringVar(value="0")
        self.blocked_var = tk.StringVar(value="0")
        self.cache_entries_var = tk.StringVar(value=str(self.cache.entry_count()))

        self.status_var = tk.StringVar(value="Ready — select a folder to begin")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_detail_var = tk.StringVar(value="Idle")
        self.progress_note_var = tk.StringVar(
            value="The first scan reads metadata with MkPFS. Later scans reuse unchanged files from the local metadata cache."
        )

        self.preset_var = tk.StringVar(value=self.PRESET_PPSA)
        self.include_id_var = tk.BooleanVar(value=True)
        self.include_title_var = tk.BooleanVar(value=False)
        self.include_version_var = tk.BooleanVar(value=False)
        self.version_format_var = tk.StringVar(value=self.VERSION_COMPACT)
        self.version_prefix_var = tk.BooleanVar(value=True)
        self.create_folder_var = tk.BooleanVar(value=False)
        self.output_preview_var = tk.StringVar(value="PPSA01285.ffpfsc")

        self.parsed_items: list[tuple[Path, GameMetadata]] = []
        self.scan_errors: list[tuple[Path, str]] = []
        self.plan: list[RenamePlanItem] = []
        self.last_scan_total = 0
        self.last_cache_hits = 0
        self.last_mkpfs_reads = 0
        self.last_scan_elapsed = 0.0
        self.last_worker_count = 1

        self._build_ui()
        self._refresh_output_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)

        self._build_sidebar(shell)

        content = ttk.Frame(shell, padding=(24, 20, 24, 18))
        content.pack(side="left", fill="both", expand=True)

        header = ttk.Frame(content)
        header.pack(fill="x")
        ttk.Label(header, text="Library Renamer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Cached metadata, safe output templates, collision checks and explicit rename confirmation.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self._build_stats(content)
        self._build_configuration(content)
        self._build_progress(content)
        self._build_table(content)
        self._build_footer(content)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=COLORS["sidebar"], width=220, bd=0, highlightthickness=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=22, pady=(22, 24))
        tk.Label(
            brand,
            text="FFPFSC",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand,
            text="RENAMER",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand,
            text=f"v{__version__}",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self._sidebar_heading(sidebar, "WORKSPACE")
        active = tk.Frame(sidebar, bg=COLORS["accent_soft"], height=42)
        active.pack(fill="x")
        active.pack_propagate(False)
        tk.Frame(active, bg=COLORS["accent"], width=3).pack(side="left", fill="y")
        tk.Label(
            active,
            text="  ▦  Library",
            bg=COLORS["accent_soft"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(side="left", fill="both", expand=True, padx=(10, 0))

        self._sidebar_heading(sidebar, "ENGINE", top=24)
        engine_box = self._sidebar_box(sidebar)
        tk.Label(
            engine_box,
            text="MkPFS",
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        engine_ok = mkpfs_available()
        tk.Label(
            engine_box,
            text="●  Detected" if engine_ok else "●  Not installed",
            bg=COLORS["surface"],
            fg=COLORS["success"] if engine_ok else COLORS["danger"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        self._sidebar_heading(sidebar, "CACHE", top=20)
        cache_box = self._sidebar_box(sidebar)
        tk.Label(
            cache_box,
            text="Metadata DB",
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 1))
        tk.Label(
            cache_box,
            textvariable=self.cache_entries_var,
            bg=COLORS["surface"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12)
        tk.Label(
            cache_box,
            text="cached file records",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 6))
        clear = tk.Label(
            cache_box,
            text="Clear cache",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
            anchor="w",
        )
        clear.pack(fill="x", padx=12, pady=(0, 10))
        clear.bind("<Button-1>", lambda _event: self._clear_cache())

        legal = tk.Frame(sidebar, bg=COLORS["sidebar"])
        legal.pack(side="bottom", fill="x", padx=18, pady=18)
        tk.Frame(legal, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 12))
        tk.Label(
            legal,
            text="Homebrew & personal backup tool",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            legal,
            text="Not affiliated with Sony Interactive Entertainment",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 7),
            wraplength=175,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _sidebar_heading(parent: tk.Widget, text: str, top: int = 0) -> None:
        tk.Label(
            parent,
            text=text,
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(top, 7))

    @staticmethod
    def _sidebar_box(parent: tk.Widget) -> tk.Frame:
        box = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        box.pack(fill="x", padx=16, pady=(4, 0))
        return box

    def _build_stats(self, parent: ttk.Frame) -> None:
        stats = ttk.Frame(parent)
        stats.pack(fill="x", pady=(18, 12))
        for column in range(4):
            stats.columnconfigure(column, weight=1, uniform="stats")

        cards = (
            ("FILES FOUND", self.files_var, COLORS["accent"]),
            ("FROM CACHE", self.cached_var, COLORS["warning"]),
            ("READY", self.ready_var, COLORS["success"]),
            ("BLOCKED / ERRORS", self.blocked_var, COLORS["danger"]),
        )
        for column, (label, variable, accent) in enumerate(cards):
            card = tk.Frame(
                stats,
                bg=COLORS["panel"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            card.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 5, 0 if column == 3 else 5),
            )
            tk.Frame(card, bg=accent, height=2).pack(fill="x")
            tk.Label(
                card,
                textvariable=variable,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 19, "bold"),
                anchor="w",
            ).pack(fill="x", padx=13, pady=(10, 0))
            tk.Label(
                card,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            ).pack(fill="x", padx=13, pady=(0, 10))

    def _build_configuration(self, parent: ttk.Frame) -> None:
        area = ttk.Frame(parent)
        area.pack(fill="x")
        area.columnconfigure(0, weight=5, uniform="configuration")
        area.columnconfigure(1, weight=6, uniform="configuration")

        library = ttk.Frame(area, style="Card.TFrame", padding=15)
        library.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        output = ttk.Frame(area, style="Card.TFrame", padding=15)
        output.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self._build_library_controls(library)
        self._build_output_controls(output)

    def _build_library_controls(self, card: ttk.Frame) -> None:
        ttk.Label(card, text="FFPFSC library", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="Choose a folder. Cached unchanged files are skipped automatically.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 9))

        path_row = ttk.Frame(card, style="Card.TFrame")
        path_row.pack(fill="x")
        self.folder_entry = tk.Entry(
            path_row,
            textvariable=self.folder_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 7))
        self.browse_button = ttk.Button(
            path_row,
            text="Browse",
            style="Secondary.TButton",
            command=self._browse,
        )
        self.browse_button.pack(side="left")

        options = ttk.Frame(card, style="Card.TFrame")
        options.pack(fill="x", pady=(10, 0))
        self.recursive_check = ttk.Checkbutton(
            options,
            text="Include subfolders",
            variable=self.recursive_var,
        )
        self.recursive_check.pack(side="left")
        ttk.Label(options, text="Workers", style="CardMuted.TLabel").pack(side="left", padx=(18, 6))
        self.worker_combo = ttk.Combobox(
            options,
            textvariable=self.worker_var,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=17,
            style="Performance.TCombobox",
        )
        self.worker_combo.pack(side="left")
        self.scan_button = ttk.Button(
            options,
            text="Scan library",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.pack(side="right")

    def _build_output_controls(self, card: ttk.Frame) -> None:
        ttk.Label(card, text="Output format", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="Change the template after scanning without reading the FFPFSC files again.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        row1 = ttk.Frame(card, style="Card.TFrame")
        row1.pack(fill="x")
        ttk.Label(row1, text="Preset", style="CardMuted.TLabel").pack(side="left", padx=(0, 6))
        self.preset_combo = ttk.Combobox(
            row1,
            textvariable=self.preset_var,
            values=(self.PRESET_PPSA, self.PRESET_TITLE, self.PRESET_FULL, self.PRESET_CUSTOM),
            state="readonly",
            width=24,
            style="Performance.TCombobox",
        )
        self.preset_combo.pack(side="left")
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)

        self.id_check = ttk.Checkbutton(
            row1,
            text="PPSA",
            variable=self.include_id_var,
            command=self._custom_output_changed,
        )
        self.id_check.pack(side="left", padx=(12, 5))
        self.title_check = ttk.Checkbutton(
            row1,
            text="Title",
            variable=self.include_title_var,
            command=self._custom_output_changed,
        )
        self.title_check.pack(side="left", padx=5)
        self.version_check = ttk.Checkbutton(
            row1,
            text="Version",
            variable=self.include_version_var,
            command=self._custom_output_changed,
        )
        self.version_check.pack(side="left", padx=5)

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=(7, 0))
        self.version_combo = ttk.Combobox(
            row2,
            textvariable=self.version_format_var,
            values=(self.VERSION_COMPACT, self.VERSION_ORIGINAL),
            state="readonly",
            width=24,
            style="Performance.TCombobox",
        )
        self.version_combo.pack(side="left")
        self.version_combo.bind("<<ComboboxSelected>>", self._output_setting_changed)
        self.version_prefix_check = ttk.Checkbutton(
            row2,
            text="Prefix 'v'",
            variable=self.version_prefix_var,
            command=self._output_setting_changed,
        )
        self.version_prefix_check.pack(side="left", padx=(10, 6))
        self.folder_check = ttk.Checkbutton(
            row2,
            text="Create folder",
            variable=self.create_folder_var,
            command=self._output_setting_changed,
        )
        self.folder_check.pack(side="left", padx=6)

        preview = tk.Frame(
            card,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        preview.pack(fill="x", pady=(8, 0))
        tk.Label(
            preview,
            textvariable=self.output_preview_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["accent_hover"],
            font=("Consolas", 9),
            anchor="w",
        ).pack(fill="x", padx=9, pady=7)

    def _build_progress(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
        card.pack(fill="x", pady=(10, 0))
        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Analysis progress", style="CardTitle.TLabel").pack(side="left")
        self.cancel_button = ttk.Button(
            top,
            text="Cancel",
            style="Danger.TButton",
            command=self._cancel_scan,
            state="disabled",
        )
        self.cancel_button.pack(side="right")
        ttk.Label(
            card,
            textvariable=self.progress_note_var,
            style="CardMuted.TLabel",
            wraplength=950,
            justify="left",
        ).pack(fill="x", pady=(3, 7))
        ttk.Progressbar(
            card,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="Scan.Horizontal.TProgressbar",
        ).pack(fill="x")
        ttk.Label(card, textvariable=self.progress_detail_var, style="CardInfo.TLabel").pack(
            fill="x", pady=(5, 0)
        )

    def _build_table(self, parent: ttk.Frame) -> None:
        table_card = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        table_card.pack(fill="both", expand=True, pady=(10, 10))

        columns = ("file", "title_id", "title", "version", "output", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", style="Library.Treeview")
        headings = {
            "file": "Current file",
            "title_id": "Title ID",
            "title": "Title",
            "version": "Version",
            "output": "Proposed output",
            "status": "Status",
        }
        widths = {
            "file": 200,
            "title_id": 100,
            "title": 220,
            "version": 100,
            "output": 390,
            "status": 95,
        }
        for name in columns:
            self.tree.heading(name, text=headings[name])
            self.tree.column(name, width=widths[name], minwidth=80, anchor="w")

        for tag, color in (
            ("ready", COLORS["success"]),
            ("unchanged", COLORS["muted"]),
            ("collision", COLORS["danger"]),
            ("invalid", COLORS["danger"]),
            ("error", COLORS["danger"]),
        ):
            self.tree.tag_configure(tag, foreground=color)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").pack(side="left")
        self.rename_button = ttk.Button(
            footer,
            text="Apply rename plan",
            style="Primary.TButton",
            command=self._rename,
            state="disabled",
        )
        self.rename_button.pack(side="right")

    # ---------------------------------------------------------- output plan
    def _current_naming_options(self) -> NamingOptions:
        return NamingOptions(
            include_title_id=bool(self.include_id_var.get()),
            include_title=bool(self.include_title_var.get()),
            include_version=bool(self.include_version_var.get()),
            compact_version=self.version_format_var.get() == self.VERSION_COMPACT,
            version_prefix=bool(self.version_prefix_var.get()),
            create_folder=bool(self.create_folder_var.get()),
        )

    def _apply_preset(self, _event=None) -> None:
        preset = self.preset_var.get()
        if preset == self.PRESET_PPSA:
            self.include_id_var.set(True)
            self.include_title_var.set(False)
            self.include_version_var.set(False)
        elif preset == self.PRESET_TITLE:
            self.include_id_var.set(True)
            self.include_title_var.set(True)
            self.include_version_var.set(False)
        elif preset == self.PRESET_FULL:
            self.include_id_var.set(True)
            self.include_title_var.set(True)
            self.include_version_var.set(True)
        self._output_setting_changed()

    def _custom_output_changed(self) -> None:
        self.preset_var.set(self.PRESET_CUSTOM)
        self._output_setting_changed()

    def _output_setting_changed(self, _event=None) -> None:
        self._refresh_output_preview()
        if self.parsed_items or self.scan_errors:
            self._rebuild_output_plan(option_change=True)

    def _refresh_output_preview(self) -> None:
        options = self._current_naming_options()
        try:
            if self.parsed_items:
                metadata = self.parsed_items[0][1]
                stem = build_output_stem(metadata, options)
                filename = f"{stem}.ffpfsc"
                preview = f"{stem}\\{filename}" if options.create_folder else filename
            else:
                preview = example_output(options)
        except ValueError as exc:
            preview = f"Invalid format: {exc}"
        self.output_preview_var.set(preview)

    @staticmethod
    def _display_destination(item: RenamePlanItem) -> str:
        if item.target_directory is not None:
            return f"{item.target_directory.name}\\{item.destination.name}"
        return item.destination.name

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        options = self._current_naming_options()
        self.plan = build_rename_plan(self.parsed_items, options)
        self._refresh_output_preview()

        for row in self.tree.get_children():
            self.tree.delete(row)

        for item in self.plan:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.source.name,
                    item.metadata.title_id,
                    item.metadata.title_name or "-",
                    item.metadata.content_version or item.metadata.master_version or "-",
                    self._display_destination(item),
                    item.status.value.upper(),
                ),
                tags=(item.status.value,),
            )

        for image, detail in self.scan_errors:
            self.tree.insert(
                "",
                "end",
                values=(image.name, "-", detail, "-", "-", "ERROR"),
                tags=("error",),
            )

        ready = sum(item.status is PlanStatus.READY for item in self.plan)
        unchanged = sum(item.status is PlanStatus.UNCHANGED for item in self.plan)
        blocked = sum(
            item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}
            for item in self.plan
        ) + len(self.scan_errors)

        self.ready_var.set(str(ready))
        self.blocked_var.set(str(blocked))
        self.rename_button.configure(state="normal" if ready and not blocked else "disabled")

        if option_change:
            self.status_var.set(
                f"Output plan updated instantly — {ready} ready, {unchanged} unchanged, {blocked} blocked"
            )

    # --------------------------------------------------------------- cache
    def _clear_cache(self) -> None:
        if self._scan_active:
            return
        if not messagebox.askyesno(
            "Clear metadata cache",
            "Delete all cached FFPFSC metadata?\n\nThe next scan will read every file again with MkPFS.",
        ):
            return
        self.cache.clear()
        self.cache_entries_var.set("0")
        self.cached_var.set("0")
        messagebox.showinfo("PS5 FFPFSC Renamer", "Metadata cache cleared.")

    # --------------------------------------------------------------- scan
    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select FFPFSC folder")
        if selected:
            self.folder_var.set(selected)

    def _scan(self) -> None:
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showwarning("PS5 FFPFSC Renamer", "Select a folder first.")
            return
        if not mkpfs_available():
            messagebox.showerror(
                "MkPFS required",
                "MkPFS is not installed.\n\nInstall it with:\npython -m pip install mkpfs==0.0.9",
            )
            return

        self.cancel_event.clear()
        self.parsed_items = []
        self.scan_errors = []
        self.plan = []
        self.files_var.set("0")
        self.cached_var.set("0")
        self.ready_var.set("0")
        self.blocked_var.set("0")
        self.progress_var.set(0.0)
        self.progress_detail_var.set("Discovering .ffpfsc files...")
        self.progress_note_var.set(
            "Checking the local SQLite metadata cache first. Only new or changed files will be opened with MkPFS."
        )
        self.status_var.set("Scanning library...")
        self.rename_button.configure(state="disabled")
        for row in self.tree.get_children():
            self.tree.delete(row)

        self._set_scan_controls(True)
        threading.Thread(
            target=self._scan_worker,
            args=(Path(folder_text), bool(self.recursive_var.get()), self.worker_var.get()),
            daemon=True,
        ).start()

    def _set_scan_controls(self, active: bool) -> None:
        self._scan_active = active
        if active:
            self.scan_button.configure(state="disabled")
            self.browse_button.configure(state="disabled")
            self.folder_entry.configure(state="disabled")
            self.worker_combo.configure(state="disabled")
            self.recursive_check.state(["disabled"])
            self.cancel_button.configure(state="normal")
        else:
            self.scan_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.folder_entry.configure(state="normal")
            self.worker_combo.configure(state="readonly")
            self.recursive_check.state(["!disabled"])
            self.cancel_button.configure(state="disabled")

    def _cancel_scan(self) -> None:
        if not self._scan_active:
            return
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("Cancelling...")
        self.progress_note_var.set("Cancellation requested. No rename operation will be performed.")

    @staticmethod
    def _resolve_worker_count(setting: str, total_misses: int) -> int:
        if total_misses <= 1:
            return 1
        if setting == "Auto":
            return min(2, total_misses)
        if setting.startswith("4"):
            return min(4, total_misses)
        if setting.startswith("2"):
            return min(2, total_misses)
        return 1

    def _scan_worker(self, folder: Path, recursive: bool, worker_setting: str) -> None:
        started_at = time.monotonic()
        try:
            images = scan_ffpfsc(folder, recursive=recursive)
        except Exception as exc:
            self.after(0, lambda detail=str(exc): self._scan_failed(detail))
            return

        total = len(images)
        cached_items: list[tuple[Path, GameMetadata]] = []
        misses: list[Path] = []

        self.after(0, lambda: self.files_var.set(str(total)))

        for index, image in enumerate(images, start=1):
            if self.cancel_event.is_set():
                self.after(0, lambda: self._scan_cancelled(len(cached_items), total))
                return
            try:
                lookup = self.cache.lookup(image)
            except Exception:
                lookup = None

            if lookup is not None and lookup.hit and lookup.metadata is not None:
                cached_items.append((image, lookup.metadata))
            else:
                misses.append(image)

            self.after(
                0,
                lambda done=index, hits=len(cached_items), new=len(misses): self._cache_check_progress(
                    done, total, hits, new
                ),
            )

        cache_hits = len(cached_items)
        workers = self._resolve_worker_count(worker_setting, len(misses))
        self.after(
            0,
            lambda: self._analysis_started(total, cache_hits, len(misses), workers),
        )

        parsed = list(cached_items)
        errors: list[tuple[Path, str]] = []
        completed = cache_hits
        mkpfs_reads = 0

        if not misses:
            self.after(
                0,
                lambda: self._scan_complete(
                    parsed, errors, total, started_at, workers, cache_hits, 0
                ),
            )
            return

        def read_one(image: Path) -> GameMetadata:
            return read_metadata(
                image,
                timeout=120,
                cancel_event=self.cancel_event,
                use_cache=False,
            )

        if workers == 1:
            for image in misses:
                if self.cancel_event.is_set():
                    break
                try:
                    metadata = read_one(image)
                    parsed.append((image, metadata))
                    try:
                        self.cache.store(image, metadata)
                    except Exception:
                        pass
                except MetadataReadCancelled:
                    break
                except MetadataReadError as exc:
                    errors.append((image, str(exc)))
                except Exception as exc:
                    errors.append((image, f"Unexpected error: {exc}"))

                completed += 1
                mkpfs_reads += 1
                self.after(
                    0,
                    lambda done=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                        done, total, started_at, name, workers, cache_hits, reads
                    ),
                )
        else:
            executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ffpfsc-reader")
            future_to_image = {executor.submit(read_one, image): image for image in misses}
            pending = set(future_to_image)
            try:
                while pending and not self.cancel_event.is_set():
                    done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                    for future in done:
                        image = future_to_image[future]
                        try:
                            metadata = future.result()
                            parsed.append((image, metadata))
                            try:
                                self.cache.store(image, metadata)
                            except Exception:
                                pass
                        except MetadataReadCancelled:
                            self.cancel_event.set()
                            break
                        except MetadataReadError as exc:
                            errors.append((image, str(exc)))
                        except Exception as exc:
                            errors.append((image, f"Unexpected error: {exc}"))

                        completed += 1
                        mkpfs_reads += 1
                        self.after(
                            0,
                            lambda done_count=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                                done_count, total, started_at, name, workers, cache_hits, reads
                            ),
                        )
            finally:
                if self.cancel_event.is_set():
                    for future in pending:
                        future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(completed, total))
            return

        self.after(
            0,
            lambda: self._scan_complete(
                parsed, errors, total, started_at, workers, cache_hits, mkpfs_reads
            ),
        )

    def _cache_check_progress(self, checked: int, total: int, hits: int, new: int) -> None:
        self.files_var.set(str(total))
        self.cached_var.set(str(hits))
        self.status_var.set(f"Checking metadata cache {checked}/{total}...")
        self.progress_detail_var.set(
            f"Cache check {checked}/{total} • {hits} unchanged cached • {new} new/changed"
        )

    def _analysis_started(self, total: int, cache_hits: int, misses: int, workers: int) -> None:
        self.cached_var.set(str(cache_hits))
        if total == 0:
            self.progress_note_var.set("No .ffpfsc files were found in the selected location.")
            self.progress_detail_var.set("0 files found")
            return

        if misses == 0:
            self.progress_note_var.set(
                f"All {total} files matched the cache. No MkPFS metadata reads are required."
            )
        else:
            self.progress_note_var.set(
                f"{cache_hits} file(s) reused from cache; {misses} new or changed file(s) require MkPFS. "
                f"Using {workers} worker(s)."
            )
        self.progress_var.set((cache_hits / total * 100.0) if total else 0.0)
        self.progress_detail_var.set(
            f"{cache_hits}/{total} complete • cache {cache_hits} • MkPFS pending {misses}"
        )

    def _progress_update(
        self,
        completed: int,
        total: int,
        started_at: float,
        last_name: str,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        elapsed = max(0.0, time.monotonic() - started_at)
        percent = (completed / total * 100.0) if total else 0.0
        self.progress_var.set(percent)

        eta = "calculating..."
        active_done = max(0, completed - cache_hits)
        if active_done > 0 and completed < total:
            rate = active_done / elapsed if elapsed > 0 else 0
            if rate > 0:
                eta = self._format_duration((total - completed) / rate)
        elif completed >= total:
            eta = "00:00"

        self.progress_detail_var.set(
            f"{completed}/{total} • {percent:.0f}% • cache {cache_hits} • MkPFS {mkpfs_reads} • "
            f"elapsed {self._format_duration(elapsed)} • ETA {eta} • {workers} worker(s)"
        )
        self.status_var.set(f"Analyzing {completed}/{total} — {last_name}")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds_int = max(0, int(seconds))
        hours, remainder = divmod(seconds_int, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

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
        self.parsed_items = parsed
        self.scan_errors = errors
        self.last_scan_total = total
        self.last_cache_hits = cache_hits
        self.last_mkpfs_reads = mkpfs_reads
        self.last_worker_count = workers
        self.last_scan_elapsed = max(0.0, time.monotonic() - started_at)

        self.files_var.set(str(total))
        self.cached_var.set(str(cache_hits))
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self.progress_var.set(100.0 if total else 0.0)
        self.progress_note_var.set(
            f"Scan complete: {cache_hits} reused from cache, {mkpfs_reads} read with MkPFS. "
            "You can now change the output format instantly without rescanning."
        )
        self.progress_detail_var.set(
            f"Completed in {self._format_duration(self.last_scan_elapsed)} • cache {cache_hits} • "
            f"MkPFS {mkpfs_reads} • {workers} worker(s)"
        )
        self._set_scan_controls(False)
        self._rebuild_output_plan()
        self.status_var.set(
            f"Scan complete — {cache_hits} cached, {mkpfs_reads} new/changed, {len(errors)} metadata error(s)"
        )

    def _scan_failed(self, detail: str) -> None:
        self._set_scan_controls(False)
        self.blocked_var.set("1")
        self.progress_note_var.set("The scan stopped because an error occurred.")
        self.progress_detail_var.set(detail)
        self.status_var.set("Scan failed")
        messagebox.showerror("PS5 FFPFSC Renamer", detail)

    def _scan_cancelled(self, completed: int, total: int) -> None:
        self.plan = []
        self._set_scan_controls(False)
        percent = (completed / total * 100.0) if total else 0.0
        self.progress_var.set(percent)
        self.progress_note_var.set("Analysis cancelled. No filenames or FFPFSC contents were changed.")
        self.progress_detail_var.set(f"Stopped after {completed}/{total} file(s) • {percent:.0f}%")
        self.status_var.set(f"Cancelled — {completed}/{total} processed")
        self.rename_button.configure(state="disabled")

    # -------------------------------------------------------------- rename
    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
            return

        folder_mode = bool(self.create_folder_var.get())
        action = "create folders and move/rename" if folder_mode else "rename"
        if not messagebox.askyesno(
            "Confirm output plan",
            f"Apply the plan to {len(ready)} file(s)?\n\nThe program will {action} the selected files. "
            "FFPFSC contents are never rewritten or recompressed.",
        ):
            return

        try:
            completed = apply_rename_plan(self.plan)
        except Exception as exc:
            messagebox.showerror("PS5 FFPFSC Renamer", str(exc))
            return

        for old_path, new_path in completed:
            try:
                self.cache.update_path_after_rename(old_path, new_path)
            except Exception:
                pass
        self.cache_entries_var.set(str(self.cache.entry_count()))

        messagebox.showinfo(
            "PS5 FFPFSC Renamer",
            f"Completed {len(completed)} file operation(s).\n\nA rescan will now use the cache and should be much faster.",
        )
        self._scan()


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
