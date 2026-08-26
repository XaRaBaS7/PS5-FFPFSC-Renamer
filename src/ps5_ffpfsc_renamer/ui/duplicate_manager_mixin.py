from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..duplicate_manager import summarize_duplicate_groups
from ..library_view import human_size


class DuplicateManagerMixin:
    """In-memory duplicate-group manager and focused selection shortcuts."""

    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return

        def cascade(label: str) -> tk.Menu | None:
            end = menubar.index("end")
            if end is None:
                return None
            for index in range(int(end) + 1):
                try:
                    if menubar.type(index) != "cascade":
                        continue
                    if str(menubar.entrycget(index, "label")) != label:
                        continue
                    menu = self.nametowidget(menubar.entrycget(index, "menu"))
                    return menu if isinstance(menu, tk.Menu) else None
                except tk.TclError:
                    continue
            return None

        tools = cascade("Tools")
        if tools is not None:
            try:
                tools.insert_command(4, label="Duplicate Manager...", command=self._show_duplicate_manager)
            except tk.TclError:
                tools.add_command(label="Duplicate Manager...", command=self._show_duplicate_manager)

        edit = cascade("Edit")
        if edit is not None:
            try:
                edit.insert_command(
                    3,
                    label="Select problem rows\tCtrl+Shift+P",
                    command=self._select_problem_rows,
                )
                edit.insert_command(
                    4,
                    label="Select duplicate rows\tCtrl+Shift+D",
                    command=self._select_duplicate_rows,
                )
            except tk.TclError:
                edit.add_command(label="Select problem rows", command=self._select_problem_rows)
                edit.add_command(label="Select duplicate rows", command=self._select_duplicate_rows)

    def _install_shortcuts(self) -> None:
        super()._install_shortcuts()
        self.bind("<Control-Shift-P>", lambda _event: self._shortcut_select_problems(), add="+")
        self.bind("<Control-Shift-D>", lambda _event: self._shortcut_select_duplicates(), add="+")

    def _shortcut_select_problems(self) -> str:
        if not self._scan_active:
            self._select_problem_rows()
        return "break"

    def _shortcut_select_duplicates(self) -> str:
        if not self._scan_active:
            self._select_duplicate_rows()
        return "break"

    def _select_filtered_rows(self, filter_name: str, *, label: str) -> int:
        selected_filter = filter_name.strip().upper()
        if selected_filter not in tuple(getattr(self, "FILTERS", ())):
            raise ValueError(f"Unsupported selection filter: {filter_name}")
        self.search_var.set("")
        self.filter_var.set(selected_filter)
        self._render_records()
        rows = tuple(self.tree.get_children(""))
        if rows:
            self.tree.selection_set(*rows)
            self.tree.focus(rows[0])
            self.tree.see(rows[0])
        self.status_var.set(f"{len(rows)} {label} selected")
        return len(rows)

    def _select_duplicate_rows(self) -> int:
        return self._select_filtered_rows("DUPLICATES", label="duplicate row(s)")

    def _select_problem_rows(self) -> int:
        return self._select_filtered_rows("PROBLEMS", label="problem row(s)")

    def _focus_duplicate_group(self, title_id: str) -> int:
        normalized = title_id.strip().upper()
        if not normalized or normalized == "-":
            return 0
        self.search_var.set(normalized)
        self.filter_var.set("DUPLICATES")
        self._render_records()
        rows = tuple(
            row
            for row, record in self._row_records.items()
            if record.view.title_id.strip().upper() == normalized
        )
        if rows:
            self.tree.selection_set(*rows)
            self.tree.focus(rows[0])
            self.tree.see(rows[0])
        self.status_var.set(f"Duplicate group {normalized}: {len(rows)} file(s) selected")
        return len(rows)

    def _show_duplicate_manager(self) -> None:
        summaries = summarize_duplicate_groups(record.view for record in self._all_records)
        if not summaries:
            messagebox.showinfo(
                "Duplicate Manager",
                "No duplicate Title ID groups are present in the current library results.",
                parent=self,
            )
            return

        window = tk.Toplevel(self)
        window.title("Duplicate Manager")
        window.geometry("1080x660")
        window.minsize(860, 540)
        window.transient(self)

        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Duplicate Manager", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Duplicate groups are summarized from the current in-memory library. "
                "No FFPFSC data is read until Compare group is requested."
            ),
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        ttk.Label(
            outer,
            text=f"{len(summaries)} group(s) • {sum(item.file_count for item in summaries)} file(s)",
            style="CardInfo.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        panes = ttk.Panedwindow(outer, orient="vertical")
        panes.pack(fill="both", expand=True)
        top = ttk.Frame(panes, style="Card.TFrame", padding=8)
        bottom = ttk.Frame(panes, style="Card.TFrame", padding=8)
        panes.add(top, weight=3)
        panes.add(bottom, weight=2)

        groups = ttk.Treeview(
            top,
            columns=("id", "title", "files", "versions", "size", "check", "status"),
            show="headings",
            selectmode="browse",
            style="Library.Treeview",
        )
        specs = (
            ("id", "Title ID", 110),
            ("title", "Title", 250),
            ("files", "Files", 55),
            ("versions", "Versions", 145),
            ("size", "Known total", 105),
            ("check", "Size check", 115),
            ("status", "Statuses", 170),
        )
        for column, heading, width in specs:
            groups.heading(column, text=heading)
            groups.column(column, width=width, minwidth=50, anchor="w")
        groups.pack(fill="both", expand=True)

        summary_ids = {item.title_id for item in summaries}
        for item in summaries:
            size = human_size(item.total_size)
            if item.known_size_files != item.file_count:
                size += f" ({item.known_size_files}/{item.file_count})"
            groups.insert(
                "",
                "end",
                iid=item.title_id,
                values=(item.title_id, item.title, item.file_count, item.versions_text, size, item.size_state, item.status_text),
            )

        files = ttk.Treeview(
            bottom,
            columns=("path", "version", "size", "status"),
            show="headings",
            selectmode="extended",
            style="Library.Treeview",
        )
        for column, heading, width in (
            ("path", "Path", 650),
            ("version", "Version", 110),
            ("size", "Size", 95),
            ("status", "Status", 95),
        ):
            files.heading(column, text=heading)
            files.column(column, width=width, minwidth=70, anchor="w")
        files.pack(fill="both", expand=True)

        def selected_id() -> str | None:
            selection = groups.selection()
            if not selection:
                return None
            value = str(selection[0]).upper()
            return value if value in summary_ids else None

        def refresh(_event=None) -> None:
            for row in files.get_children(""):
                files.delete(row)
            title_id = selected_id()
            if title_id is None:
                return
            records = sorted(
                self._duplicate_groups.get(title_id, ()),
                key=lambda record: str(record.view.source).casefold(),
            )
            for record in records:
                files.insert(
                    "",
                    "end",
                    values=(self._display_source(record.view.source), record.view.version, human_size(record.view.size), record.view.status),
                )

        def show_group() -> None:
            title_id = selected_id()
            if title_id is not None:
                self._focus_duplicate_group(title_id)

        def compare_group() -> None:
            title_id = selected_id()
            if title_id is not None:
                self._compare_duplicates(title_id)

        groups.bind("<<TreeviewSelect>>", refresh)
        groups.bind("<Double-1>", lambda _event: show_group())
        groups.bind("<Return>", lambda _event: show_group())
        groups.selection_set(summaries[0].title_id)
        groups.focus(summaries[0].title_id)
        refresh()

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Show group in library", command=show_group).pack(side="left")
        ttk.Button(buttons, text="Compare group...", command=compare_group).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Select all duplicates", command=self._select_duplicate_rows).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
