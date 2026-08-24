from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui_v2 import RenamerApp as RenamerAppV2
from .naming import (
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    NamingOptions,
)
from .theme import COLORS


class RenamerApp(RenamerAppV2):
    """Desktop UI with a visual, reorderable filename builder."""

    PRESET_PPSA = "PPSA only (compatible)"
    PRESET_TITLE_ONLY = "Title only"
    PRESET_TITLE = "PPSA → Title"
    PRESET_TITLE_PPSA = "Title → PPSA"
    PRESET_FULL = "PPSA → Title → Version"
    PRESET_TITLE_PPSA_VERSION = "Title → PPSA → Version"
    PRESET_TITLE_VERSION_PPSA = "Title → Version → PPSA"
    PRESET_CUSTOM = "Custom"

    def __init__(self) -> None:
        # Plain Python state is safe to create before tk.Tk is initialized by
        # the parent. The parent creates all Tk variables before _build_ui().
        self.component_order = [
            COMPONENT_TITLE_ID,
            COMPONENT_TITLE,
            COMPONENT_VERSION,
        ]
        super().__init__()

    def _build_output_controls(self, card: ttk.Frame) -> None:
        ttk.Label(card, text="Filename Builder", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="Choose what to include and move items up/down. Top item appears first in the filename.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        preset_row = ttk.Frame(card, style="Card.TFrame")
        preset_row.pack(fill="x")
        ttk.Label(preset_row, text="Quick preset", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 6)
        )
        self.preset_combo = ttk.Combobox(
            preset_row,
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

        ttk.Label(
            card,
            text="Filename order",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(10, 5))

        self.order_editor = tk.Frame(card, bg=COLORS["panel"])
        self.order_editor.pack(fill="x")
        self._render_order_editor()

        options_row = ttk.Frame(card, style="Card.TFrame")
        options_row.pack(fill="x", pady=(9, 0))
        ttk.Label(options_row, text="Version", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 6)
        )
        self.version_combo = ttk.Combobox(
            options_row,
            textvariable=self.version_format_var,
            values=(self.VERSION_COMPACT, self.VERSION_ORIGINAL),
            state="readonly",
            width=21,
            style="Performance.TCombobox",
        )
        self.version_combo.pack(side="left")
        self.version_combo.bind("<<ComboboxSelected>>", self._output_setting_changed)

        self.version_prefix_check = ttk.Checkbutton(
            options_row,
            text="Prefix 'v'",
            variable=self.version_prefix_var,
            command=self._output_setting_changed,
        )
        self.version_prefix_check.pack(side="left", padx=(9, 5))

        self.folder_check = ttk.Checkbutton(
            options_row,
            text="Create folder",
            variable=self.create_folder_var,
            command=self._output_setting_changed,
        )
        self.folder_check.pack(side="left", padx=5)

        ttk.Label(card, text="Live preview", style="CardMuted.TLabel").pack(
            anchor="w", pady=(9, 4)
        )
        preview = tk.Frame(
            card,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        preview.pack(fill="x")
        tk.Label(
            preview,
            textvariable=self.output_preview_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["accent_hover"],
            font=("Consolas", 9),
            anchor="w",
        ).pack(fill="x", padx=9, pady=7)

    def _component_definition(self, component: str):
        if component == COMPONENT_TITLE_ID:
            return "PPSA / Title ID", "PPSA01285", self.include_id_var
        if component == COMPONENT_TITLE:
            return "Game title", "Returnal", self.include_title_var
        if component == COMPONENT_VERSION:
            return "Version", "v1.0", self.include_version_var
        raise ValueError(f"Unknown filename component: {component}")

    def _render_order_editor(self) -> None:
        for child in self.order_editor.winfo_children():
            child.destroy()

        for index, component in enumerate(self.component_order):
            label, sample, variable = self._component_definition(component)
            row = tk.Frame(
                self.order_editor,
                bg=COLORS["panel_alt"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            row.pack(fill="x", pady=(0, 4))

            number = tk.Label(
                row,
                text=str(index + 1),
                bg=COLORS["accent_soft"],
                fg=COLORS["accent_hover"],
                font=("Segoe UI", 9, "bold"),
                width=3,
            )
            number.pack(side="left", fill="y", ipady=6)

            check = ttk.Checkbutton(
                row,
                text=label,
                variable=variable,
                command=self._component_enabled_changed,
            )
            check.pack(side="left", padx=(8, 5))

            tk.Label(
                row,
                text=sample,
                bg=COLORS["panel_alt"],
                fg=COLORS["muted"],
                font=("Consolas", 8),
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(4, 8))

            down = ttk.Button(
                row,
                text="↓",
                width=3,
                style="Secondary.TButton",
                command=lambda i=index: self._move_component(i, 1),
            )
            down.pack(side="right", padx=(2, 5), pady=3)
            if index == len(self.component_order) - 1:
                down.configure(state="disabled")

            up = ttk.Button(
                row,
                text="↑",
                width=3,
                style="Secondary.TButton",
                command=lambda i=index: self._move_component(i, -1),
            )
            up.pack(side="right", padx=2, pady=3)
            if index == 0:
                up.configure(state="disabled")

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

    def _current_naming_options(self) -> NamingOptions:
        return NamingOptions(
            include_title_id=bool(self.include_id_var.get()),
            include_title=bool(self.include_title_var.get()),
            include_version=bool(self.include_version_var.get()),
            compact_version=self.version_format_var.get() == self.VERSION_COMPACT,
            version_prefix=bool(self.version_prefix_var.get()),
            create_folder=bool(self.create_folder_var.get()),
            component_order=tuple(self.component_order),
        )

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
