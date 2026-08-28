from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import COLORS


class WorkspaceLayoutMixin:
    """Compact top configuration, styled command bar and separated footer."""

    WORKSPACE_AUTO_COLLAPSE_MS = 8000

    def __init__(self) -> None:
        self._workspace_pages: dict[str, ttk.Frame] = {}
        self._workspace_tab_widgets: dict[str, dict[str, tk.Widget]] = {}
        self._workspace_active_tab = "library"
        self._workspace_shell: tk.Frame | None = None
        self._workspace_pages_frame: ttk.Frame | None = None
        self._workspace_hint_label: tk.Label | None = None
        self._workspace_collapse_job: str | None = None
        self._workspace_config_expanded = True
        self._footer_apply_button: ttk.Button | None = None
        super().__init__()

        # Ask for a taller result list. The Treeview still expands naturally
        # with the window, while the auto-collapsing configuration area returns
        # additional vertical space after the user stops interacting with it.
        try:
            self.tree.configure(height=24)
        except (AttributeError, tk.TclError):
            pass

        # ProductMenuMixin owns the canonical callbacks. The styled command bar
        # clones those menus into button-owned popup menus so Windows receives
        # valid menu ownership while the original visual treatment is retained.
        if not isinstance(getattr(self, "_product_menu", None), tk.Menu):
            self._build_product_menu()

    def _build_configuration(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        shell.pack(fill="x")
        self._workspace_shell = shell

        nav = tk.Frame(shell, bg=COLORS["panel"])
        nav.pack(fill="x", padx=12, pady=(9, 0))

        tk.Label(
            nav,
            text="CONFIGURATION",
            bg=COLORS["panel"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 12))

        pages = ttk.Frame(shell, style="Card.TFrame", padding=(12, 9, 12, 11))
        pages.pack(fill="x")
        self._workspace_pages_frame = pages

        library = ttk.Frame(pages, style="Card.TFrame")
        rename = ttk.Frame(pages, style="Card.TFrame")
        self._workspace_pages = {"library": library, "rename": rename}

        self._build_library_controls(library)
        self._build_output_controls(rename)

        for key, title, note in (
            ("library", "Library setup", "Folders, scan and performance"),
            ("rename", "Rename builder", "Filename and library organization"),
        ):
            tab = tk.Frame(
                nav,
                bg=COLORS["panel"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                cursor="hand2",
            )
            tab.pack(side="left", padx=(0, 6))
            marker = tk.Frame(tab, bg=COLORS["panel"], width=3)
            marker.pack(side="left", fill="y")
            text = tk.Frame(tab, bg=COLORS["panel"], cursor="hand2")
            text.pack(side="left", padx=9, pady=5)
            title_label = tk.Label(
                text,
                text=title,
                bg=COLORS["panel"],
                fg=COLORS["text_soft"],
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
            )
            title_label.pack(anchor="w")
            note_label = tk.Label(
                text,
                text=note,
                bg=COLORS["panel"],
                fg=COLORS["muted_dark"],
                font=("Segoe UI", 7),
                cursor="hand2",
            )
            note_label.pack(anchor="w")
            for widget in (tab, marker, text, title_label, note_label):
                widget.bind(
                    "<Button-1>",
                    lambda _event, selected=key: self._show_workspace_tab(selected),
                )
            self._workspace_tab_widgets[key] = {
                "frame": tab,
                "marker": marker,
                "text": text,
                "title": title_label,
                "note": note_label,
            }

        self._workspace_hint_label = tk.Label(
            nav,
            text="Settings auto-collapse after inactivity to give the library list more space.",
            bg=COLORS["panel"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8),
        )
        self._workspace_hint_label.pack(side="right", padx=(10, 0))

        self._show_workspace_tab("library")
        self._bind_workspace_activity(shell)
        self._schedule_workspace_collapse()

    def _build_progress(self, parent: ttk.Frame) -> None:
        """Keep Scan available even while the configuration body is collapsed."""
        super()._build_progress(parent)

        old_scan = getattr(self, "scan_button", None)
        cancel = getattr(self, "cancel_button", None)
        if not isinstance(cancel, ttk.Button):
            return
        top = cancel.master
        if not isinstance(top, ttk.Frame):
            return

        if isinstance(old_scan, ttk.Button):
            try:
                old_scan.destroy()
            except tk.TclError:
                pass

        try:
            cancel.pack_forget()
        except tk.TclError:
            return

        self.scan_button = ttk.Button(
            top,
            text="Scan now  F5",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.pack(side="right")
        cancel.pack(side="right", padx=(0, 6))

    def _bind_workspace_activity(self, widget: tk.Misc) -> None:
        """Reset the inactivity timer for real interaction inside configuration."""
        for sequence in ("<Button-1>", "<KeyPress>", "<MouseWheel>", "<FocusIn>"):
            try:
                widget.bind(sequence, self._workspace_interaction, add="+")
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._bind_workspace_activity(child)

    def _workspace_interaction(self, _event=None) -> None:
        pages = self._workspace_pages_frame
        if pages is None:
            return
        try:
            if pages.winfo_manager():
                self._schedule_workspace_collapse()
        except tk.TclError:
            pass

    def _cancel_workspace_collapse(self) -> None:
        job = self._workspace_collapse_job
        self._workspace_collapse_job = None
        if job is None:
            return
        try:
            self.after_cancel(job)
        except tk.TclError:
            pass

    def _schedule_workspace_collapse(self) -> None:
        self._cancel_workspace_collapse()
        try:
            self._workspace_collapse_job = self.after(
                self.WORKSPACE_AUTO_COLLAPSE_MS,
                self._collapse_workspace_configuration,
            )
        except tk.TclError:
            self._workspace_collapse_job = None

    def _collapse_workspace_configuration(self) -> None:
        self._workspace_collapse_job = None
        pages = self._workspace_pages_frame
        if pages is None:
            return
        try:
            if pages.winfo_manager():
                pages.pack_forget()
            self._workspace_config_expanded = False
            if self._workspace_hint_label is not None:
                self._workspace_hint_label.configure(
                    text="Configuration collapsed • click Library setup or Rename builder to reopen."
                )
        except tk.TclError:
            pass

    def _show_workspace_tab(self, key: str) -> None:
        if key not in self._workspace_pages:
            return

        pages = self._workspace_pages_frame
        if pages is not None:
            try:
                if not pages.winfo_manager():
                    pages.pack(fill="x")
                self._workspace_config_expanded = True
            except tk.TclError:
                pass

        self._workspace_active_tab = key
        for page_key, page in self._workspace_pages.items():
            if page_key == key:
                page.pack(fill="x")
            else:
                page.pack_forget()

        for tab_key, widgets in self._workspace_tab_widgets.items():
            active = tab_key == key
            background = COLORS["accent_soft"] if active else COLORS["panel"]
            border = COLORS["accent"] if active else COLORS["border"]
            widgets["frame"].configure(bg=background, highlightbackground=border)
            widgets["marker"].configure(bg=COLORS["accent"] if active else background)
            widgets["text"].configure(bg=background)
            widgets["title"].configure(
                bg=background,
                fg=COLORS["accent_hover"] if active else COLORS["text_soft"],
            )
            widgets["note"].configure(bg=background)

        if self._workspace_hint_label is not None:
            try:
                self._workspace_hint_label.configure(
                    text="Settings auto-collapse after inactivity to give the library list more space."
                )
            except tk.TclError:
                pass
        self._schedule_workspace_collapse()

    def _build_footer(self, parent: ttk.Frame) -> None:
        # Give the footer its own visual breathing room instead of making the
        # author credit look attached to the last Treeview row.
        spacer = tk.Frame(parent, bg=COLORS["bg"], height=8)
        spacer.pack(fill="x")
        separator = tk.Frame(parent, bg=COLORS["border"], height=1)
        separator.pack(fill="x")

        footer = tk.Frame(parent, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(8, 4))
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        author_box = tk.Frame(
            footer,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        author_box.pack(side="right", padx=(14, 0), pady=2)
        tk.Label(
            author_box,
            text="PROJECT BY",
            bg=COLORS["surface"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 7, "bold"),
        ).pack(side="left", padx=(10, 5), pady=6)
        author = tk.Label(
            author_box,
            text="XaRaBaS  ↗",
            bg=COLORS["surface"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        author.pack(side="left", padx=(0, 10), pady=6)
        author.bind("<Button-1>", self._open_repository)
        author.bind("<Enter>", lambda _event: author.configure(fg=COLORS["text"]))
        author.bind("<Leave>", lambda _event: author.configure(fg=COLORS["accent_hover"]))

        # Keep a safe fallback CTA until the modern results-toolbar CTA is
        # installed. It is hidden automatically when that primary CTA exists.
        self.rename_button = ttk.Button(
            footer,
            text="Apply changes",
            style="RenamePrimary.TButton",
            command=self._rename,
            state="disabled",
        )
        self.rename_button.pack(side="right", padx=(12, 0))
        self._footer_apply_button = self.rename_button

    def _install_rename_plan_button(self) -> None:
        super()._install_rename_plan_button()
        if getattr(self, "_rename_plan_button", None) is None:
            return
        fallback = self._footer_apply_button
        if fallback is not None:
            try:
                fallback.pack_forget()
            except tk.TclError:
                pass

    @staticmethod
    def _menu_entry_option(menu: tk.Menu, index: int, option: str) -> str:
        try:
            return str(menu.entrycget(index, option))
        except tk.TclError:
            return ""

    def _clone_command_menu(self, source: tk.Menu, parent: tk.Misc) -> tk.Menu:
        """Clone a product menu into a popup owned by the visible Menubutton.

        The old styled command row reused popup menus whose Tk parent was the
        hidden top-level menubar. That ownership mismatch can leave a visible
        Menubutton that does not post anything on Windows after the native menu
        is detached. Each visible button now owns its popup while command
        execution delegates back to the canonical ProductMenuMixin menu entry.
        """
        clone = tk.Menu(parent, tearoff=False)
        try:
            end = source.index("end")
        except tk.TclError:
            end = None
        if end is None:
            self._style_popup_menu(clone)
            return clone

        for index in range(int(end) + 1):
            try:
                kind = source.type(index)
            except tk.TclError:
                continue

            if kind == "separator":
                clone.add_separator()
                continue

            label = self._menu_entry_option(source, index, "label")
            state = self._menu_entry_option(source, index, "state") or "normal"

            if kind == "cascade":
                child_name = self._menu_entry_option(source, index, "menu")
                try:
                    child = self.nametowidget(child_name)
                except (tk.TclError, KeyError):
                    child = None
                if isinstance(child, tk.Menu):
                    child_clone = self._clone_command_menu(child, clone)
                    clone.add_cascade(label=label, menu=child_clone, state=state)
                continue

            if kind != "command":
                continue

            options: dict[str, object] = {
                "label": label,
                "state": state,
                "command": lambda menu=source, item=index: menu.invoke(item),
            }
            accelerator = self._menu_entry_option(source, index, "accelerator")
            if accelerator:
                options["accelerator"] = accelerator
            image = self._menu_entry_option(source, index, "image")
            if image:
                options["image"] = image
                compound = self._menu_entry_option(source, index, "compound")
                if compound:
                    options["compound"] = compound
            clone.add_command(**options)

        self._style_popup_menu(clone)
        return clone

    def _install_modern_command_bar(self) -> None:
        """Restore the styled File/Edit/Tools/Help row with reliable popups."""
        if self._modern_command_bar is not None:
            return
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return
        header = self._find_main_header()
        if header is None:
            return
        content = header.master

        bar = tk.Frame(content, bg=COLORS["bg"], bd=0, highlightthickness=0)
        try:
            try:
                bar.pack(fill="x", pady=(0, 7), before=header)
            except tk.TclError:
                bar.pack(fill="x", pady=(0, 7))

            try:
                end = menubar.index("end")
            except tk.TclError:
                end = None
            if end is None:
                bar.destroy()
                return

            for index in range(int(end) + 1):
                try:
                    if menubar.type(index) != "cascade":
                        continue
                    label = str(menubar.entrycget(index, "label"))
                    menu_name = menubar.entrycget(index, "menu")
                    submenu = self.nametowidget(menu_name)
                except (tk.TclError, KeyError):
                    continue
                if not isinstance(submenu, tk.Menu):
                    continue

                button = tk.Menubutton(
                    bar,
                    text=label,
                    indicatoron=False,
                    bg=COLORS["bg"],
                    fg=COLORS["text_soft"],
                    activebackground=COLORS["panel_hover"],
                    activeforeground=COLORS["text"],
                    relief="flat",
                    bd=0,
                    highlightthickness=0,
                    padx=9,
                    pady=5,
                    font=("Segoe UI", 9),
                    cursor="hand2",
                )
                popup = self._clone_command_menu(submenu, button)
                button.configure(menu=popup)
                button.pack(side="left", padx=(0, 2))

            # Keep the native menu as a safe fallback until every styled button
            # has a valid child-owned popup, then hide only its presentation.
            if not bar.winfo_children():
                bar.destroy()
                return
            self.configure(menu="")
            self._modern_command_bar = bar
        except Exception:
            try:
                bar.destroy()
            except tk.TclError:
                pass
            try:
                self.configure(menu=menubar)
            except tk.TclError:
                pass
            raise

    def _install_creator_credit(self) -> None:
        """The footer owns the only creator credit; do not overlay the table."""
        self._creator_credit_label = None
