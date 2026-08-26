from __future__ import annotations

import os
import subprocess
import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import __version__
from ..branding import BRAND_ICON_NAME, BRAND_LOGO_NAME, load_brand_photo
from ..ffpfsc_reader import mkpfs_source_description
from ..theme import COLORS


class ShellMiscMixin:
    """Small shell actions plus application branding."""

    def __init__(self) -> None:
        self._brand_icon_photo: tk.PhotoImage | None = None
        self._brand_sidebar_photo: tk.PhotoImage | None = None
        self._about_window: tk.Toplevel | None = None
        super().__init__()
        self._apply_window_branding()

    def _build_ui(self) -> None:
        super()._build_ui()
        self._install_sidebar_brand()

    def _apply_window_branding(self) -> None:
        photo = load_brand_photo(self, BRAND_ICON_NAME)
        if photo is None:
            return
        self._brand_icon_photo = photo
        try:
            self.iconphoto(True, photo)
        except tk.TclError:
            pass

    def _install_sidebar_brand(self) -> None:
        # The sidebar has roughly 176 px of usable width after its existing
        # horizontal padding.  The 640 px lockup at 1/4 scale fits without
        # clipping while remaining readable on standard Windows DPI settings.
        photo = load_brand_photo(self, BRAND_LOGO_NAME, subsample=4)
        if photo is None:
            return

        def walk(widget: tk.Misc):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        for candidate in walk(self):
            if not isinstance(candidate, tk.Frame):
                continue
            labels = [child for child in candidate.winfo_children() if isinstance(child, tk.Label)]
            texts = {str(label.cget("text")) for label in labels}
            if not {"FFPFSC", "RENAMER"}.issubset(texts):
                continue

            version = next(
                (label for label in labels if str(label.cget("text")).startswith("v")),
                None,
            )
            if version is not None:
                version.pack_forget()
            for label in labels:
                if str(label.cget("text")) in {"FFPFSC", "RENAMER"}:
                    label.destroy()

            self._brand_sidebar_photo = photo
            tk.Label(
                candidate,
                image=photo,
                bg=COLORS["sidebar"],
                bd=0,
                highlightthickness=0,
                anchor="w",
            ).pack(fill="x")
            if version is not None:
                version.pack(fill="x", pady=(4, 0))
            return

    def _select_all_rows(self) -> None:
        rows = self.tree.get_children()
        if rows:
            self.tree.selection_set(rows)
            self.status_var.set(f"Selected {len(rows)} visible result(s)")

    def _open_app_data_folder(self) -> None:
        folder = self.cache.db_path.parent
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _show_about(self) -> None:
        existing = self._about_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        window = tk.Toplevel(self)
        self._about_window = window
        window.title("About PS5 FFPFSC Renamer")
        window.geometry("640x470")
        window.resizable(False, False)
        window.transient(self)

        icon = self._brand_icon_photo or load_brand_photo(window, BRAND_ICON_NAME)
        if icon is not None:
            try:
                window.iconphoto(True, icon)
            except tk.TclError:
                pass

        outer = ttk.Frame(window, padding=22)
        outer.pack(fill="both", expand=True)

        logo = load_brand_photo(window, BRAND_LOGO_NAME, subsample=2)
        if logo is not None:
            label = tk.Label(
                outer,
                image=logo,
                bg=COLORS["background"],
                bd=0,
                highlightthickness=0,
            )
            label.image = logo  # type: ignore[attr-defined]
            label.pack(anchor="center", pady=(0, 12))
        else:
            ttk.Label(outer, text="PS5 FFPFSC Renamer", style="Title.TLabel").pack(anchor="center")

        ttk.Label(
            outer,
            text=f"Version {__version__}",
            style="Subtitle.TLabel",
        ).pack(anchor="center", pady=(0, 14))

        ttk.Label(
            outer,
            text=(
                "Windows utility for inspecting PS5 FFPFSC metadata and applying safe, "
                "reviewable library renames without rewriting or recompressing the image payload."
            ),
            wraplength=560,
            justify="center",
        ).pack(anchor="center", pady=(0, 12))

        ttk.Label(
            outer,
            text=(
                "Homebrew & Personal Backup Tool\n"
                "For games/content you legally own and dumped yourself. The software does not "
                "download games, decrypt retail packages, bypass DRM or provide copyrighted content."
            ),
            style="CardMuted.TLabel",
            wraplength=560,
            justify="center",
        ).pack(anchor="center", pady=(0, 12))

        ttk.Label(
            outer,
            text=f"MkPFS: {mkpfs_source_description()}",
            style="CardInfo.TLabel",
            wraplength=560,
            justify="center",
        ).pack(anchor="center", pady=(0, 14))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", side="bottom")
        ttk.Button(
            buttons,
            text="GitHub repository",
            command=lambda: webbrowser.open("https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer"),
        ).pack(side="left")
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

        def closed() -> None:
            self._about_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", closed)
