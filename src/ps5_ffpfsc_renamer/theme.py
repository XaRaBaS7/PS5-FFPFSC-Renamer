from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Original dark-violet design tokens. The visual direction is intentionally
# compatible with modern PS5 utility UIs without copying another project's
# theme module or layout.
COLORS = {
    "bg": "#0b0911",
    "sidebar": "#100d18",
    "surface": "#15111f",
    "panel": "#1c1728",
    "panel_alt": "#251e34",
    "panel_hover": "#2c2340",
    "border": "#342a48",
    "text": "#f2eff8",
    "text_soft": "#d7d1e1",
    "muted": "#9f97ad",
    "muted_dark": "#746c82",
    "accent": "#a875d6",
    "accent_hover": "#c08ce8",
    "accent_soft": "#241632",
    "success": "#57c7a5",
    "success_soft": "#10271f",
    "warning": "#d8ae63",
    "warning_soft": "#2a2110",
    "danger": "#df6877",
    "danger_soft": "#2b1219",
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        ".",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["panel_alt"],
        bordercolor=COLORS["border"],
        troughcolor=COLORS["surface"],
        font=("Segoe UI", 10),
    )
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
    style.configure("Surface.TFrame", background=COLORS["surface"])
    style.configure("Card.TFrame", background=COLORS["panel"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure(
        "Title.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI", 23, "bold"),
    )
    style.configure(
        "AccentTitle.TLabel",
        background=COLORS["sidebar"],
        foreground=COLORS["accent"],
        font=("Segoe UI", 16, "bold"),
    )
    style.configure(
        "SidebarMuted.TLabel",
        background=COLORS["sidebar"],
        foreground=COLORS["muted_dark"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "SidebarBody.TLabel",
        background=COLORS["sidebar"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "CardTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI", 11, "bold"),
    )
    style.configure(
        "CardMuted.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "CardInfo.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text_soft"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "StatNumber.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI", 21, "bold"),
    )
    style.configure(
        "StatLabel.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )

    style.configure(
        "Primary.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        padding=(15, 9),
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLORS["accent_hover"]), ("disabled", COLORS["panel_alt"])],
        foreground=[("disabled", COLORS["muted_dark"])],
    )
    style.configure(
        "Secondary.TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text_soft"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        padding=(12, 8),
    )
    style.map("Secondary.TButton", background=[("active", COLORS["panel_hover"])])
    style.configure(
        "Danger.TButton",
        background=COLORS["danger_soft"],
        foreground=COLORS["danger"],
        bordercolor=COLORS["danger"],
        borderwidth=1,
        padding=(12, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Danger.TButton",
        background=[("active", COLORS["danger"]), ("disabled", COLORS["panel_alt"])],
        foreground=[("active", "#ffffff"), ("disabled", COLORS["muted_dark"])],
    )

    style.configure(
        "Library.Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text_soft"],
        rowheight=31,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Library.Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        borderwidth=0,
        relief="flat",
        padding=(8, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Library.Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#ffffff")],
    )

    style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text_soft"])
    style.map("TCheckbutton", background=[("active", COLORS["panel"])])
    style.configure(
        "Performance.TCombobox",
        fieldbackground=COLORS["panel_alt"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(7, 6),
    )
    style.map(
        "Performance.TCombobox",
        fieldbackground=[("readonly", COLORS["panel_alt"])],
        foreground=[("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["panel_alt"])],
        selectforeground=[("readonly", COLORS["text"])],
    )
    style.configure(
        "Scan.Horizontal.TProgressbar",
        troughcolor=COLORS["panel_alt"],
        background=COLORS["accent"],
        bordercolor=COLORS["panel_alt"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        thickness=10,
    )
    style.configure(
        "Activity.Horizontal.TProgressbar",
        troughcolor=COLORS["panel_alt"],
        background=COLORS["success"],
        bordercolor=COLORS["panel_alt"],
        lightcolor=COLORS["success"],
        darkcolor=COLORS["success"],
        thickness=7,
    )
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["panel_alt"],
        troughcolor=COLORS["surface"],
        bordercolor=COLORS["surface"],
        arrowcolor=COLORS["muted"],
    )
    return style
