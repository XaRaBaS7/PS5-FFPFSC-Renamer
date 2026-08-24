from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui_v2 import RenamerApp as RenamerAppV2
from .naming import (
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    FOLDER_ALWAYS_NEW,
    FOLDER_FILE_ONLY,
    FOLDER_SMART,
    NamingOptions,
    build_output_stem,
    effective_folder_handling,
    example_output,
)
from .theme import COLORS


class RenamerApp(RenamerAppV2):
    """Desktop UI with a compact, reorderable filename builder."""

    PRESET_PPSA = "PPSA only (compatible)"
    PRESET_TITLE_ONLY = "Title only"
    PRESET_TITLE = "PPSA → Title"
    PRESET_TITLE_PPSA = "Title → PPSA"
    PRESET_FULL = "PPSA → Title → Version"
    PRESET_TITLE_PPSA_VERSION = "Title → PPSA → Version"
    PRESET_TITLE_VERSION_PPSA = "Title → Version → PPSA"
    PRESET_CUSTOM = "Custom"

    FOLDER_SMART_LABEL = "Smart (recommended)"
    FOLDER_FILE_ONLY_LABEL = "File only"
    FOLDER_ALWAYS_NEW_LABEL = "Always create new folder"

    def __init__(self) -> None:
        self.component_order = [
            COMPONENT_TITLE_ID,
            COMPONENT_TITLE,
            COMPONENT_VERSION,
        ]
        super().__init__()

    # ----------------------------------------------------------- compact UI
    def _build_output_controls(self, card: ttk.Frame) -> None:
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Filename Builder", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Build the output name without rescanning files.",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        # Preset and folder handling share one compact row.
        controls = ttk.Frame(card, style="Card.TFrame")
        controls.pack(fill="x", pady=(7, 0))

        ttk.Label(controls, text="Preset", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 5)
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
            width=24,
            style="Performance.TCombobox",
        )
        self.preset_combo.pack(side="left")
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)

        ttk.Label(controls, text="Folder", style="CardMuted.TLabel").pack(
            side="left", padx=(14, 5)
        )
        self.folder_mode_var = tk.StringVar(value=self.FOLDER_SMART_LABEL)
        self.folder_mode_combo = ttk.Combobox(
            controls,
            textvariable=self.folder_mode_var,
            values=(
                self.FOLDER_SMART_LABEL,
                self.FOLDER_FILE_ONLY_LABEL,
                self.FOLDER_ALWAYS_NEW_LABEL,
            ),
            state="readonly",
            width=22,
            style="Performance.TCombobox",
        )
        self.folder_mode_combo.pack(side="left", fill="x", expand=True)
        self.folder_mode_combo.bind("<<ComboboxSelected>>", self._folder_mode_changed)

        self.folder_help_var = tk.StringVar()
        ttk.Label(
            card,
            textvariable=self.folder_help_var,
            style="CardMuted.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))
        self._update_folder_help()

        order_header = ttk.Frame(card, style="Card.TFrame")
        order_header.pack(fill="x", pady=(7, 3))
        ttk.Label(order_header, text="Filename order", style="CardMuted.TLabel").pack(side="left")
        ttk.Label(
            order_header,
            text="Use ← / → to choose what comes first.",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(8, 0))

        # The three filename components are horizontal instead of three tall
        # rows. This keeps the results table as the dominant part of the app.
        self.order_editor = tk.Frame(card, bg=COLORS["panel"])
        self.order_editor.pack(fill="x")
        self._render_order_editor()

        settings = ttk.Frame(card, style="Card.TFrame")
        settings.pack(fill="x", pady=(7, 0))
        ttk.Label(settings, text="Version", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 5)
        )
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

        ttk.Label(settings, text="Preview", style="CardMuted.TLabel").pack(
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

    def _build_progress(self, parent: ttk.Frame) -> None:
        """Compact progress card so completed scans leave room for results."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 7))
        card.pack(fill="x", pady=(8, 0))

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Analysis", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(
            top,
            textvariable=self.progress_detail_var,
            style="CardInfo.TLabel",
        ).pack(side="left", padx=(10, 0))
        self.cancel_button = ttk.Button(
            top,
            text="Cancel",
            style="Danger.TButton",
            command=self._cancel_scan,
            state="disabled",
        )
        self.cancel_button.pack(side="right")

        ttk.Progressbar(
            card,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="Scan.Horizontal.TProgressbar",
        ).pack(fill="x", pady=(5, 0))

        ttk.Label(
            card,
            textvariable=self.progress_note_var,
            style="CardMuted.TLabel",
            wraplength=1050,
            justify="left",
        ).pack(fill="x", pady=(3, 0))

    def _build_table(self, parent: ttk.Frame) -> None:
        super()._build_table(parent)
        # Request a useful number of visible rows. The table still expands and
        # shrinks with the window, but now gets priority over configuration UI.
        self.tree.configure(height=14)

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
        label = self.folder_mode_var.get()
        if label == self.FOLDER_FILE_ONLY_LABEL:
            return FOLDER_FILE_ONLY
        if label == self.FOLDER_ALWAYS_NEW_LABEL:
            return FOLDER_ALWAYS_NEW
        return FOLDER_SMART

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
        self._update_folder_help()
        self._output_setting_changed()

    def _update_folder_help(self) -> None:
        mode = self._folder_mode()
        if mode == FOLDER_SMART:
            text = "Smart: loose → new folder • dedicated folder → rename folder + file • multiple FFPFSC → blocked"
        elif mode == FOLDER_FILE_ONLY:
            text = "File only: rename the .ffpfsc and leave folder names unchanged."
        else:
            text = "Always new: create a generated subfolder and move the .ffpfsc into it."
        self.folder_help_var.set(text)

    def _refresh_output_preview(self) -> None:
        options = self._current_naming_options()
        try:
            if self.parsed_items:
                metadata = self.parsed_items[0][1]
                stem = build_output_stem(metadata, options)
                filename = f"{stem}.ffpfsc"
                if effective_folder_handling(options) == FOLDER_FILE_ONLY:
                    preview = filename
                else:
                    preview = f"{stem}\\{filename}"
            else:
                preview = example_output(options)
        except ValueError as exc:
            preview = f"Invalid format: {exc}"
        self.output_preview_var.set(preview)

    def _apply_preset(self, _event=None) -> None:
        preset = self.preset_var.get()

        presets = {
            self.PRESET_PPSA: (
                (True, False, False),
                (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
            ),
            self.PRESET_TITLE_ONLY: (
                (False, True, False),
                (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION),
            ),
            self.PRESET_TITLE: (
                (True, True, False),
                (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
            ),
            self.PRESET_TITLE_PPSA: (
                (True, True, False),
                (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION),
            ),
            self.PRESET_FULL: (
                (True, True, True),
                (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
            ),
            self.PRESET_TITLE_PPSA_VERSION: (
                (True, True, True),
                (COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION),
            ),
            self.PRESET_TITLE_VERSION_PPSA: (
                (True, True, True),
                (COMPONENT_TITLE, COMPONENT_VERSION, COMPONENT_TITLE_ID),
            ),
        }

        config = presets.get(preset)
        if config is not None:
            enabled, order = config
            self.include_id_var.set(enabled[0])
            self.include_title_var.set(enabled[1])
            self.include_version_var.set(enabled[2])
            self.component_order[:] = order
            self._render_order_editor()

        self._output_setting_changed()


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
