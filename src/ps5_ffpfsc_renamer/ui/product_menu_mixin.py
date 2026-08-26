from __future__ import annotations

import tkinter as tk

from ..theme import COLORS


class ProductMenuMixin:
    """Top-level File/Edit/Tools/Help product menu."""

    def _build_product_menu(self) -> None:
        menubar = tk.Menu(self, tearoff=False)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="Scan library\tF5",
            image=self._icon("scan", 16, COLORS["accent_hover"]),
            compound="left",
            command=self._scan,
        )
        file_menu.add_separator()
        export_menu = tk.Menu(file_menu, tearoff=False)
        export_icon = self._icon("export", 16, COLORS["accent_hover"])
        export_menu.add_command(
            label="Full library as CSV...",
            image=export_icon,
            compound="left",
            command=lambda: self._export_library("csv", visible_only=False),
        )
        export_menu.add_command(
            label="Full library as JSON...",
            image=export_icon,
            compound="left",
            command=lambda: self._export_library("json", visible_only=False),
        )
        export_menu.add_separator()
        export_menu.add_command(
            label="Visible results as CSV...",
            command=lambda: self._export_library("csv", visible_only=True),
        )
        export_menu.add_command(
            label="Visible results as JSON...",
            command=lambda: self._export_library("json", visible_only=True),
        )
        export_menu.add_separator()
        export_menu.add_command(
            label="Selected results as CSV...",
            command=lambda: self._export_selected("csv"),
        )
        export_menu.add_command(
            label="Selected results as JSON...",
            command=lambda: self._export_selected("json"),
        )
        file_menu.add_cascade(label="Export", menu=export_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._close_with_settings)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(
            label="Undo last rename\tCtrl+Z",
            image=self._icon("undo", 16, COLORS["accent_hover"]),
            compound="left",
            command=self._undo_last_rename,
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Select all results\tCtrl+A", command=self._select_all_rows)
        edit_menu.add_command(label="Focus search\tCtrl+F", command=self._shortcut_find)
        edit_menu.add_command(
            label="Clear search/filter/selection\tEsc",
            command=self._shortcut_clear_view,
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

        tools_menu = tk.Menu(menubar, tearoff=False)
        tools_menu.add_command(
            label="Options...",
            image=self._icon("options", 16, COLORS["accent_hover"]),
            compound="left",
            command=self._show_options,
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Operation history...", command=self._show_history_window)
        tools_menu.add_command(
            label="Library health report",
            image=self._icon("health", 16, COLORS["success"]),
            compound="left",
            command=self._show_library_health,
        )
        tools_menu.add_command(
            label="Re-analyze PARTIAL / ERROR...",
            image=self._icon("scan", 16, COLORS["warning"]),
            compound="left",
            command=self._reanalyze_problem_rows,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Cache Manager...",
            image=self._icon("cache", 16, COLORS["text_soft"]),
            compound="left",
            command=self._show_cache_manager,
        )
        tools_menu.add_command(
            label="MkPFS engine...",
            image=self._icon("engine", 16, COLORS["text_soft"]),
            compound="left",
            command=self._show_mkpfs_settings,
        )
        tools_menu.add_command(label="Open app data folder", command=self._open_app_data_folder)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)
        self._product_menu = menubar
