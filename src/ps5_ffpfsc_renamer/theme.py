from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#0d0b14",
    "surface": "#15111f",
    "panel": "#1d1729",
    "panel_alt": "#251e35",
    "border": "#342a47",
    "text": "#f2eff8",
    "muted": "#a59db3",
    "accent": "#a875d6",
    "accent_hover": "#bd8dea",
    "success": "#57c7a5",
    "warning": "#d8ae63",
    "danger": "#df6877",
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["surface"])
    style.configure("Card.TFrame", background=COLORS["panel"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["accent"], font=("Segoe UI", 22, "bold"))
    style.configure("Subtitle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
    style.configure("CardTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
    style.configure("CardMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])

    style.configure(
        "Primary.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        borderwidth=0,
        padding=(14, 9),
        font=("Segoe UI", 10, "bold"),
    )
    style.map("Primary.TButton", background=[("active", COLORS["accent_hover"]), ("disabled", COLORS["panel_alt"])])
    style.configure(
        "Secondary.TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=(12, 8),
    )
    style.map("Secondary.TButton", background=[("active", COLORS["border"])])

    style.configure(
        "Library.Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=30,
        borderwidth=0,
    )
    style.configure(
        "Library.Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        borderwidth=0,
        font=("Segoe UI", 9, "bold"),
    )
    style.map("Library.Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "#ffffff")])

    style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])
    style.map("TCheckbutton", background=[("active", COLORS["panel"])])
    return style
