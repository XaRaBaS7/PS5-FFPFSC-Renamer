from __future__ import annotations

import tkinter as tk


class KeyboardShortcutsMixin:
    """Desktop keyboard shortcuts for scan, navigation, export and selection."""

    TEXT_EDITING_WIDGETS = frozenset(
        {
            "Entry",
            "TEntry",
            "Text",
            "Spinbox",
            "TSpinbox",
            "TCombobox",
        }
    )

    def _install_shortcuts(self) -> None:
        self.bind("<F5>", lambda _event: self._shortcut_scan(), add="+")
        self.bind("<Control-z>", lambda event: self._shortcut_undo(event), add="+")
        self.bind("<Control-Z>", lambda event: self._shortcut_undo(event), add="+")
        self.bind("<Control-e>", lambda _event: self._shortcut_export(), add="+")
        self.bind("<Control-E>", lambda _event: self._shortcut_export(), add="+")
        self.bind("<Control-a>", lambda event: self._shortcut_select_all(event), add="+")
        self.bind("<Control-A>", lambda event: self._shortcut_select_all(event), add="+")
        self.bind("<Control-f>", lambda _event: self._shortcut_find(), add="+")
        self.bind("<Control-F>", lambda _event: self._shortcut_find(), add="+")
        self.bind("<Escape>", lambda _event: self._shortcut_clear_view(), add="+")

    def _event_targets_text_editing(self, event=None) -> bool:
        widget = getattr(event, "widget", None)
        if widget is None:
            return False
        try:
            return str(widget.winfo_class()) in self.TEXT_EDITING_WIDGETS
        except (AttributeError, tk.TclError):
            return False

    def _shortcut_scan(self) -> str:
        if not self._scan_active:
            self._scan()
        return "break"

    def _shortcut_undo(self, event=None) -> str | None:
        # Ctrl+Z inside a text-editing widget belongs to that widget. Never let
        # a text-editing gesture trigger filesystem Undo for the latest rename.
        if self._event_targets_text_editing(event):
            return None
        if not self._scan_active:
            self._undo_last_rename()
        return "break"

    def _shortcut_export(self) -> str:
        self._export_library("csv", visible_only=False)
        return "break"

    def _shortcut_select_all(self, event=None) -> str | None:
        # Preserve normal text-selection behavior while the search field or
        # another editable control owns keyboard focus.
        if self._event_targets_text_editing(event):
            return None
        self._select_all_rows()
        return "break"

    def _shortcut_find(self) -> str:
        target = str(getattr(self, "search_var", ""))
        if not target:
            return "break"
        stack = list(self.winfo_children())
        while stack:
            widget = stack.pop()
            try:
                stack.extend(widget.winfo_children())
            except tk.TclError:
                pass
            if not isinstance(widget, tk.Entry):
                continue
            try:
                if str(widget.cget("textvariable")) != target:
                    continue
                widget.focus_set()
                widget.selection_range(0, "end")
                widget.icursor("end")
                break
            except tk.TclError:
                continue
        return "break"

    def _shortcut_clear_view(self) -> str:
        if hasattr(self, "search_var"):
            self.search_var.set("")
        if hasattr(self, "filter_var"):
            self.filter_var.set("ALL")
        if hasattr(self, "tree"):
            try:
                self.tree.selection_remove(self.tree.selection())
            except tk.TclError:
                pass
        return "break"
