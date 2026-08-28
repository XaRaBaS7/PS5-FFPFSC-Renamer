from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import COLORS


class WorkspaceLayoutMixin:
    """Compact top configuration, reliable native menu and separated footer."""

    def __init__(self) -> None:
        self._workspace_pages: dict[str, ttk.Frame] = {}
        self._workspace_tab_widgets: dict[str, dict[str, tk.Widget]] = {}
        self._workspace_active_tab = "library"
        self._footer_apply_button: ttk.Button | None = None
        super().__init__()

        # The results table already expands with the window; request a taller
        # starting size now that configuration no longer occupies two columns.
        try:
            self.tree.configure(height=18)
        except (AttributeError, tk.TclError):
            pass

        # The product menu used to be repurposed by an in-app Menubutton row.
        # Build/attach the real Tk menu once, then leave it attached so its
        # commands remain valid on Windows.
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

        tk.Label(
            nav,
            text="Only one setup panel is shown at a time so the library list keeps the available space.",
            bg=COLORS["panel"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8),
        ).pack(side="right", padx=(10, 0))

        self._show_workspace_tab("library")

    def _show_workspace_tab(self, key: str) -> None:
        if key not in self._workspace_pages:
            return
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

    def _install_modern_command_bar(self) -> None:
        """Keep the native Windows/Tk menubar attached and functional."""
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return
        try:
            self.configure(menu=menubar)
        except tk.TclError:
            return
        self._modern_command_bar = None

    def _install_creator_credit(self) -> None:
        """The footer owns the only creator credit; do not overlay the table."""
        self._creator_credit_label = None
