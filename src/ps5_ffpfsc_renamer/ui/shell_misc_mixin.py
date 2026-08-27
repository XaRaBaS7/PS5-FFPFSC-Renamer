from __future__ import annotations

import os
import subprocess
import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import __version__
from ..branding import BRAND_ICON_NAME, BRAND_LOGO_NAME, load_brand_photo
from ..ffpfsc_reader import mkpfs_source_description
from ..rename_plan import PlanStatus
from ..theme import COLORS


class ShellMiscMixin:
    """Small shell actions plus application branding and modern command chrome."""

    def __init__(self) -> None:
        self._brand_icon_photo: tk.PhotoImage | None = None
        self._brand_sidebar_photo: tk.PhotoImage | None = None
        self._about_window: tk.Toplevel | None = None
        self._modern_command_bar: tk.Frame | None = None
        self._sidebar_options_button: ttk.Button | None = None
        self._rename_plan_button: ttk.Button | None = None
        super().__init__()
        self._apply_window_branding()
        try:
            self.ready_var.trace_add("write", lambda *_args: self.after_idle(self._refresh_rename_plan_button))
        except Exception:
            pass
        self.after_idle(self._install_modern_shell)

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

    @staticmethod
    def _walk_widgets(widget: tk.Misc):
        for child in widget.winfo_children():
            yield child
            yield from ShellMiscMixin._walk_widgets(child)

    @staticmethod
    def _widget_text(widget: tk.Misc) -> str:
        try:
            return str(widget.cget("text"))
        except (tk.TclError, AttributeError):
            return ""

    def _shell_warning(self, label: str, exc: BaseException) -> None:
        """Record a cosmetic-shell fallback without invoking the crash reporter."""

        try:
            self._log("WARN", f"Modern UI fallback ({label}): {type(exc).__name__}: {exc}")
        except Exception:
            pass

    def _install_modern_shell(self) -> None:
        # This layer is presentation-only. A Tk/theme/layout difference must
        # never prevent the application from starting or trigger an automatic
        # crash report. Each enhancement is therefore isolated and the legacy
        # widget remains available when its replacement cannot be installed.
        steps = (
            ("sidebar options", self._install_sidebar_options_button),
            ("central options cleanup", self._remove_legacy_central_options_button),
            ("rename action", self._install_rename_plan_button),
            ("command bar", self._install_modern_command_bar),
            ("rename action refresh", self._refresh_rename_plan_button),
        )
        for label, action in steps:
            try:
                action()
            except Exception as exc:
                self._shell_warning(label, exc)

    def _install_sidebar_brand(self) -> None:
        # The sidebar has roughly 176 px of usable width after its existing
        # horizontal padding. The 640 px lockup at 1/4 scale fits without
        # clipping while remaining readable on standard Windows DPI settings.
        photo = load_brand_photo(self, BRAND_LOGO_NAME, subsample=4)
        if photo is None:
            return

        for candidate in self._walk_widgets(self):
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

    def _install_sidebar_options_button(self) -> None:
        if self._sidebar_options_button is not None:
            return
        for candidate in self._walk_widgets(self):
            if not isinstance(candidate, tk.Frame):
                continue
            texts = {self._widget_text(child) for child in candidate.winfo_children()}
            if "Metadata DB" not in texts:
                continue
            button = ttk.Button(
                candidate,
                text="Options",
                style="SidebarAction.TButton",
                command=self._show_options,
            )
            button.pack(fill="x", padx=12, pady=(2, 12))
            self._sidebar_options_button = button
            return

    def _remove_legacy_central_options_button(self) -> None:
        for candidate in tuple(self._walk_widgets(self)):
            if not isinstance(candidate, ttk.Button):
                continue
            if candidate is self._sidebar_options_button:
                continue
            if self._widget_text(candidate).strip() in {"Options", "Options..."}:
                try:
                    candidate.destroy()
                except tk.TclError:
                    pass

    def _find_results_toolbar(self) -> ttk.Frame | None:
        for candidate in self._walk_widgets(self):
            if not isinstance(candidate, ttk.Frame):
                continue
            child_texts = {self._widget_text(child) for child in candidate.winfo_children()}
            if "Search" in child_texts and "Filter" in child_texts:
                return candidate
        return None

    def _install_rename_plan_button(self) -> None:
        if self._rename_plan_button is not None:
            return
        toolbar = self._find_results_toolbar()
        if toolbar is None:
            return

        result_label = None
        result_var_name = str(getattr(self, "result_count_var", ""))
        for child in toolbar.winfo_children():
            if not isinstance(child, ttk.Label):
                continue
            try:
                if str(child.cget("textvariable")) == result_var_name:
                    result_label = child
                    break
            except tk.TclError:
                pass

        if result_label is not None:
            result_label.pack_forget()

        button = ttk.Button(
            toolbar,
            text="Apply rename plan",
            style="RenamePrimary.TButton",
            command=self._rename,
        )
        button.pack(side="right", padx=(12, 0))
        self._rename_plan_button = button

        if result_label is not None:
            result_label.pack(side="right", padx=(0, 10))

    def _refresh_rename_plan_button(self) -> None:
        button = self._rename_plan_button
        if button is None:
            return
        try:
            ready_count = sum(1 for item in self.plan if item.status is PlanStatus.READY)
        except Exception:
            ready_count = 0
        text = f"Apply rename plan ({ready_count})" if ready_count else "Apply rename plan"
        try:
            button.configure(text=text)
            if ready_count <= 0 or bool(getattr(self, "_scan_active", False)):
                button.state(["disabled"])
            else:
                button.state(["!disabled"])
        except tk.TclError:
            pass

    def _style_popup_menu(self, menu: tk.Menu) -> None:
        try:
            menu.configure(
                bg=COLORS["panel"],
                fg=COLORS["text_soft"],
                activebackground=COLORS["accent_soft"],
                activeforeground=COLORS["text"],
                selectcolor=COLORS["accent_hover"],
                relief="flat",
                borderwidth=1,
                activeborderwidth=0,
                font=("Segoe UI", 9),
            )
        except tk.TclError:
            return

        try:
            end = menu.index("end")
        except tk.TclError:
            end = None
        if end is None:
            return
        for index in range(int(end) + 1):
            try:
                if menu.type(index) != "cascade":
                    continue
                child_name = menu.entrycget(index, "menu")
                child = self.nametowidget(child_name)
                if isinstance(child, tk.Menu):
                    self._style_popup_menu(child)
            except (tk.TclError, KeyError):
                continue

    def _find_main_header(self) -> ttk.Frame | None:
        for candidate in self._walk_widgets(self):
            if not isinstance(candidate, ttk.Label):
                continue
            if self._widget_text(candidate) != "Library Renamer":
                continue
            master = candidate.master
            return master if isinstance(master, ttk.Frame) else None
        return None

    def _install_modern_command_bar(self) -> None:
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
                self._style_popup_menu(submenu)
                button = tk.Menubutton(
                    bar,
                    text=label,
                    menu=submenu,
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
                button.pack(side="left", padx=(0, 2))

            # Detach the native Windows menu only after the replacement row is
            # fully constructed. If anything above fails, the original menu is
            # still attached and remains usable.
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
                bg=COLORS["bg"],
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
