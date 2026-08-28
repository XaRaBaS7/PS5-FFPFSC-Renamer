from __future__ import annotations

from pathlib import Path
import tkinter as tk
import webbrowser
from tkinter import ttk

from ..naming import (
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    NamingOptions,
    build_output_stem,
    effective_folder_handling,
    example_output,
    normalize_folder_handling,
)
from ..rename_plan import build_rename_plan
from ..theme import COLORS


class FilenameBuilderMixin:
    """Reorderable filename builder, library organization selector and footer."""

    REPOSITORY_URL = "https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer"

    PRESET_PPSA = "PPSA only (compatible)"
    PRESET_TITLE_ONLY = "Title only"
    PRESET_TITLE = "PPSA → Title"
    PRESET_TITLE_PPSA = "Title → PPSA"
    PRESET_FULL = "PPSA → Title → Version"
    PRESET_TITLE_PPSA_VERSION = "Title → PPSA → Version"
    PRESET_TITLE_VERSION_PPSA = "Title → Version → PPSA"
    PRESET_CUSTOM = "Custom"

    FOLDER_ONE_PER_GAME_LABEL = "One folder per game"
    FOLDER_ROOT_FLAT_LABEL = "All files in library root"
    FOLDER_KEEP_STRUCTURE_LABEL = "Keep current structure"

    # Compatibility labels used by older profile/UI helpers.
    FOLDER_SMART_LABEL = FOLDER_ONE_PER_GAME_LABEL
    FOLDER_FILE_ONLY_LABEL = FOLDER_KEEP_STRUCTURE_LABEL
    FOLDER_ALWAYS_NEW_LABEL = FOLDER_ONE_PER_GAME_LABEL

    def __init__(self) -> None:
        self.component_order = [
            COMPONENT_TITLE_ID,
            COMPONENT_TITLE,
            COMPONENT_VERSION,
        ]
        self.organization_cards: dict[str, dict[str, tk.Widget]] = {}
        super().__init__()

    def _build_output_controls(self, card: ttk.Frame) -> None:
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Filename Builder", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Choose the final filename and library layout before applying anything.",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.pack(fill="x", pady=(7, 0))
        ttk.Label(controls, text="Filename preset", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 6)
        )
        self.preset_combo = ttk.Combobox(
            controls,
            textvariable=self.preset_var,
            values=(
                self.PRESET_PPSA,
                self.PRESET_TITLE_ONLY,
                self.PRESET_TITLE,
                self.PRESET_TITLE_PPSA,
                self.PRESET_FULL,
                self.PRESET_TITLE_PPSA_VERSION,
                self.PRESET_TITLE_VERSION_PPSA,
                self.PRESET_CUSTOM,
            ),
            state="readonly",
            width=28,
            style="Performance.TCombobox",
        )
        self.preset_combo.pack(side="left")
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)

        organization_header = ttk.Frame(card, style="Card.TFrame")
        organization_header.pack(fill="x", pady=(10, 5))
        ttk.Label(
            organization_header,
            text="Library organization",
            style="CardTitle.TLabel",
        ).pack(side="left")
        ttk.Label(
            organization_header,
            text="Choose how every game should be arranged after Apply changes.",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        self.folder_mode_var = tk.StringVar(value=FOLDER_ONE_PER_GAME)
        organization_row = tk.Frame(card, bg=COLORS["panel"])
        organization_row.pack(fill="x")
        for column in range(3):
            organization_row.grid_columnconfigure(column, weight=1, uniform="organization")

        self._create_organization_card(
            organization_row,
            column=0,
            mode=FOLDER_ONE_PER_GAME,
            title=self.FOLDER_ONE_PER_GAME_LABEL,
            description="Each .ffpfsc gets its own named folder directly inside the library root.",
            badge="RECOMMENDED",
        )
        self._create_organization_card(
            organization_row,
            column=1,
            mode=FOLDER_ROOT_FLAT,
            title=self.FOLDER_ROOT_FLAT_LABEL,
            description=(
                "Move every .ffpfsc into the selected root. Empty source folders are cleaned only after successful moves."
            ),
        )
        self._create_organization_card(
            organization_row,
            column=2,
            mode=FOLDER_KEEP_STRUCTURE,
            title=self.FOLDER_KEEP_STRUCTURE_LABEL,
            description="Rename files where they are now. Existing folders and locations stay unchanged.",
        )
        self._refresh_organization_cards()

        self.folder_help_var = tk.StringVar()
        ttk.Label(
            card,
            textvariable=self.folder_help_var,
            style="CardInfo.TLabel",
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        example_box = tk.Frame(
            card,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        example_box.pack(fill="x", pady=(5, 0))
        tk.Label(
            example_box,
            text="EXAMPLE FROM CURRENT LIBRARY",
            bg=COLORS["surface"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=9, pady=(6, 1))
        self.organization_example_var = tk.StringVar()
        tk.Label(
            example_box,
            textvariable=self.organization_example_var,
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            font=("Consolas", 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=9, pady=(0, 6))
        self._update_folder_help()

        order_header = ttk.Frame(card, style="Card.TFrame")
        order_header.pack(fill="x", pady=(9, 3))
        ttk.Label(order_header, text="Filename order", style="CardMuted.TLabel").pack(side="left")
        ttk.Label(
            order_header,
            text="Use ← / → to choose what comes first.",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(8, 0))

        self.order_editor = tk.Frame(card, bg=COLORS["panel"])
        self.order_editor.pack(fill="x")
        self._render_order_editor()

        settings = ttk.Frame(card, style="Card.TFrame")
        settings.pack(fill="x", pady=(7, 0))
        ttk.Label(settings, text="Version", style="CardMuted.TLabel").pack(side="left", padx=(0, 5))
        self.version_combo = ttk.Combobox(
            settings,
            textvariable=self.version_format_var,
            values=(self.VERSION_COMPACT, self.VERSION_ORIGINAL),
            state="readonly",
            width=19,
            style="Performance.TCombobox",
        )
        self.version_combo.pack(side="left")
        self.version_combo.bind("<<ComboboxSelected>>", self._output_setting_changed)

        self.version_prefix_check = ttk.Checkbutton(
            settings,
            text="Prefix 'v'",
            variable=self.version_prefix_var,
            command=self._output_setting_changed,
        )
        self.version_prefix_check.pack(side="left", padx=(8, 12))

        ttk.Label(settings, text="Filename preview", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 5)
        )
        preview = tk.Frame(
            settings,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        preview.pack(side="left", fill="x", expand=True)
        tk.Label(
            preview,
            textvariable=self.output_preview_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["accent_hover"],
            font=("Consolas", 8),
            anchor="w",
        ).pack(fill="x", padx=7, pady=5)

    def _create_organization_card(
        self,
        parent: tk.Frame,
        *,
        column: int,
        mode: str,
        title: str,
        description: str,
        badge: str | None = None,
    ) -> None:
        frame = tk.Frame(
            parent,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            cursor="hand2",
        )
        frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 4, 0 if column == 2 else 4),
        )

        top = tk.Frame(frame, bg=COLORS["panel_alt"], cursor="hand2")
        top.pack(fill="x", padx=9, pady=(7, 1))
        indicator = tk.Label(
            top,
            text="○",
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        indicator.pack(side="left", padx=(0, 6))
        title_label = tk.Label(
            top,
            text=title,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        title_label.pack(side="left")

        badge_label: tk.Label | None = None
        if badge:
            badge_label = tk.Label(
                top,
                text=badge,
                bg=COLORS["success_soft"],
                fg=COLORS["success"],
                font=("Segoe UI", 7, "bold"),
                padx=5,
                pady=1,
                cursor="hand2",
            )
            badge_label.pack(side="right")

        description_label = tk.Label(
            frame,
            text=description,
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            justify="left",
            anchor="nw",
            wraplength=330,
            cursor="hand2",
        )
        description_label.pack(fill="x", padx=9, pady=(1, 7))

        widgets: list[tk.Widget] = [frame, top, indicator, title_label, description_label]
        if badge_label is not None:
            widgets.append(badge_label)
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, selected=mode: self._select_folder_mode(selected))

        self.organization_cards[mode] = {
            "frame": frame,
            "top": top,
            "indicator": indicator,
            "title": title_label,
            "description": description_label,
        }

    def _refresh_organization_cards(self) -> None:
        selected = self._folder_mode()
        for mode, widgets in self.organization_cards.items():
            active = mode == selected
            background = COLORS["accent_soft"] if active else COLORS["panel_alt"]
            border = COLORS["accent"] if active else COLORS["border"]
            widgets["frame"].configure(bg=background, highlightbackground=border)
            widgets["top"].configure(bg=background)
            widgets["indicator"].configure(
                bg=background,
                fg=COLORS["accent_hover"] if active else COLORS["muted"],
                text="●" if active else "○",
            )
            widgets["title"].configure(bg=background)
            widgets["description"].configure(
                bg=background,
                fg=COLORS["text_soft"] if active else COLORS["muted"],
            )

    def _select_folder_mode(self, mode: str) -> None:
        normalized = normalize_folder_handling(mode)
        if self.folder_mode_var.get() == normalized:
            return
        self.folder_mode_var.set(normalized)
        self.preset_var.set(self.PRESET_CUSTOM)
        self._refresh_organization_cards()
        self._update_folder_help()
        self._output_setting_changed()
        queue_save = getattr(self, "_queue_save_preferences", None)
        if callable(queue_save):
            queue_save()

    def _set_folder_mode(self, mode: str) -> None:
        """Apply a current or legacy profile mode without exposing legacy labels."""
        self.folder_mode_var.set(normalize_folder_handling(mode))
        self._refresh_organization_cards()
        self._update_folder_help()

    def _build_table(self, parent: ttk.Frame) -> None:
        super()._build_table(parent)
        self.tree.configure(height=12)

    def _build_footer(self, parent: ttk.Frame) -> None:
        separator = tk.Frame(parent, bg=COLORS["border"], height=1)
        separator.pack(fill="x", pady=(0, 6))

        footer = tk.Frame(parent, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(0, 4))
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self.rename_button = ttk.Button(
            footer,
            text="Apply rename plan",
            style="Primary.TButton",
            command=self._rename,
            state="disabled",
        )
        self.rename_button.pack(side="right", padx=(12, 12))

        author_box = tk.Frame(
            footer,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        author_box.pack(side="right", padx=(12, 0), pady=1)
        tk.Label(
            author_box,
            text="PROJECT BY",
            bg=COLORS["surface"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 7, "bold"),
        ).pack(side="left", padx=(9, 5), pady=5)
        author = tk.Label(
            author_box,
            text="XaRaBaS  ↗",
            bg=COLORS["surface"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        author.pack(side="left", padx=(0, 9), pady=5)
        author.bind("<Button-1>", self._open_repository)
        author.bind("<Enter>", lambda _event: author.configure(fg=COLORS["text"]))
        author.bind("<Leave>", lambda _event: author.configure(fg=COLORS["accent_hover"]))

    def _open_repository(self, _event=None) -> str:
        webbrowser.open_new_tab(self.REPOSITORY_URL)
        return "break"

    def _component_definition(self, component: str):
        if component == COMPONENT_TITLE_ID:
            return "PPSA / ID", "PPSA01285", self.include_id_var
        if component == COMPONENT_TITLE:
            return "Game title", "Returnal", self.include_title_var
        if component == COMPONENT_VERSION:
            return "Version", "v1.0", self.include_version_var
        raise ValueError(f"Unknown filename component: {component}")

    def _render_order_editor(self) -> None:
        for child in self.order_editor.winfo_children():
            child.destroy()
        for column in range(3):
            self.order_editor.grid_columnconfigure(column, weight=1, uniform="filename_order")

        for index, component in enumerate(self.component_order):
            label, _sample, variable = self._component_definition(component)
            item = tk.Frame(
                self.order_editor,
                bg=COLORS["panel_alt"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            item.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 3, 0 if index == 2 else 3),
            )
            tk.Label(
                item,
                text=str(index + 1),
                bg=COLORS["accent_soft"],
                fg=COLORS["accent_hover"],
                font=("Segoe UI", 9, "bold"),
                width=2,
            ).pack(side="left", fill="y", ipady=6)
            ttk.Checkbutton(
                item,
                text=label,
                variable=variable,
                command=self._component_enabled_changed,
            ).pack(side="left", padx=(5, 2))
            right = ttk.Button(
                item,
                text="→",
                width=2,
                style="Secondary.TButton",
                command=lambda i=index: self._move_component(i, 1),
            )
            right.pack(side="right", padx=(1, 3), pady=2)
            if index == len(self.component_order) - 1:
                right.configure(state="disabled")
            left = ttk.Button(
                item,
                text="←",
                width=2,
                style="Secondary.TButton",
                command=lambda i=index: self._move_component(i, -1),
            )
            left.pack(side="right", padx=1, pady=2)
            if index == 0:
                left.configure(state="disabled")

    def _move_component(self, index: int, direction: int) -> None:
        target = index + direction
        if target < 0 or target >= len(self.component_order):
            return
        self.component_order[index], self.component_order[target] = (
            self.component_order[target],
            self.component_order[index],
        )
        self.preset_var.set(self.PRESET_CUSTOM)
        self._render_order_editor()
        self._output_setting_changed()

    def _component_enabled_changed(self) -> None:
        self.preset_var.set(self.PRESET_CUSTOM)
        self._output_setting_changed()

    def _folder_mode(self) -> str:
        variable = getattr(self, "folder_mode_var", None)
        raw = variable.get() if variable is not None else FOLDER_ONE_PER_GAME
        return normalize_folder_handling(raw)

    def _current_naming_options(self) -> NamingOptions:
        return NamingOptions(
            include_title_id=bool(self.include_id_var.get()),
            include_title=bool(self.include_title_var.get()),
            include_version=bool(self.include_version_var.get()),
            compact_version=self.version_format_var.get() == self.VERSION_COMPACT,
            version_prefix=bool(self.version_prefix_var.get()),
            create_folder=False,
            folder_handling=self._folder_mode(),
            library_root=self.folder_var.get().strip() or None,
            component_order=tuple(self.component_order),
        )

    def _folder_mode_changed(self, _event=None) -> None:
        self._set_folder_mode(self.folder_mode_var.get())
        self._output_setting_changed()

    def _update_folder_help(self) -> None:
        mode = self._folder_mode()
        if mode == FOLDER_ONE_PER_GAME:
            text = (
                "Result: every game ends in one dedicated folder directly under its library root. "
                "A safe existing game folder is renamed when possible; otherwise the .ffpfsc is moved into a new game folder."
            )
        elif mode == FOLDER_ROOT_FLAT:
            text = (
                "Result: every .ffpfsc is renamed and moved directly into its selected library root. "
                "Only after the move succeeds, source folders are removed with an empty-folder check. "
                "Any folder containing another file, hidden file or subfolder is left untouched."
            )
        else:
            text = (
                "Result: only the .ffpfsc filename changes. The file stays in its current folder and no folder is created, moved or renamed."
            )
        if hasattr(self, "folder_help_var"):
            self.folder_help_var.set(text)
        self._refresh_organization_example()

    @staticmethod
    def _relative_preview(path: Path, root: Path | None) -> str:
        if root is not None:
            try:
                return str(path.resolve().relative_to(root.resolve()))
            except ValueError:
                pass
        return str(path)

    def _refresh_organization_example(self) -> None:
        if not hasattr(self, "organization_example_var"):
            return
        options = self._current_naming_options()
        mode = effective_folder_handling(options)
        cleanup_note = ""
        try:
            if self.parsed_items:
                source, metadata = self.parsed_items[0]
                plan = build_rename_plan([(source, metadata)], options)
                destination = plan[0].destination
                root = None
                matching_root = getattr(self, "_matching_root", None)
                if callable(matching_root):
                    root = matching_root(Path(source))
                before = self._relative_preview(Path(source), root)
                after = self._relative_preview(destination, root)
                if mode == FOLDER_ROOT_FLAT and plan[0].cleanup_directories:
                    cleanup_note = "\nCleanup empty source folders only, after move"
            else:
                stem = build_output_stem(
                    type("PreviewMetadata", (), {
                        "title_id": "PPSA01285",
                        "title_name": "Returnal",
                        "content_version": "01.000.000",
                        "master_version": "01.00",
                    })(),
                    options,
                )
                filename = f"{stem}.ffpfsc"
                before = "Old folder\\Returnal.ffpfsc"
                if mode == FOLDER_ONE_PER_GAME:
                    after = f"{stem}\\{filename}"
                elif mode == FOLDER_ROOT_FLAT:
                    after = filename
                    cleanup_note = "\nCleanup empty source folders only, after move"
                else:
                    after = f"Old folder\\{filename}"
            self.organization_example_var.set(f"Before  {before}\nAfter   {after}{cleanup_note}")
        except (OSError, ValueError) as exc:
            self.organization_example_var.set(f"Preview unavailable: {exc}")

    def _refresh_output_preview(self) -> None:
        options = self._current_naming_options()
        try:
            if self.parsed_items:
                metadata = self.parsed_items[0][1]
                stem = build_output_stem(metadata, options)
                filename = f"{stem}.ffpfsc"
                preview = (
                    f"{stem}\\{filename}"
                    if effective_folder_handling(options) == FOLDER_ONE_PER_GAME
                    else filename
                )
            else:
                preview = example_output(options)
        except ValueError as exc:
            preview = f"Invalid format: {exc}"
        self.output_preview_var.set(preview)
        self._refresh_organization_example()

    def _apply_preset(self, _event=None) -> None:
        presets = {
            self.PRESET_PPSA: ((True, False, False), (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION)),
            self.PRESET_TITLE_ONLY: ((False, True, False), (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION)),
            self.PRESET_TITLE: ((True, True, False), (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION)),
            self.PRESET_TITLE_PPSA: ((True, True, False), (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION)),
            self.PRESET_FULL: ((True, True, True), (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION)),
            self.PRESET_TITLE_PPSA_VERSION: ((True, True, True), (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION)),
            self.PRESET_TITLE_VERSION_PPSA: ((True, True, True), (COMPONENT_TITLE, COMPONENT_VERSION, COMPONENT_TITLE_ID)),
        }
        config = presets.get(self.preset_var.get())
        if config is not None:
            enabled, order = config
            self.include_id_var.set(enabled[0])
            self.include_title_var.set(enabled[1])
            self.include_version_var.set(enabled[2])
            self.component_order[:] = order
            self._render_order_editor()
        self._output_setting_changed()
