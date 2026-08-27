from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ..naming import (
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    normalize_folder_handling,
)
from ..naming_profiles import (
    BUNDLED_PROFILES,
    NamingProfile,
    all_profiles,
    delete_user_profile,
    upsert_user_profile,
)
from ..settings import AppSettings
from ..theme import COLORS


class NamingProfilesMixin:
    """Filename separators and reusable naming-profile UI/persistence."""

    def __init__(self) -> None:
        self._filename_separator = AppSettings().filename_separator
        super().__init__()

    def _apply_settings(self, settings: AppSettings) -> None:
        self._filename_separator = settings.filename_separator
        super()._apply_settings(settings)

    def _snapshot_settings(self) -> AppSettings:
        return replace(
            super()._snapshot_settings(),
            filename_separator=self._filename_separator,
        )

    def _current_naming_options(self):
        return replace(
            super()._current_naming_options(),
            separator=self._filename_separator,
        )

    def _build_output_controls(self, card: ttk.Frame) -> None:
        super()._build_output_controls(card)
        children = card.winfo_children()
        if not children:
            return
        header = children[0]
        if isinstance(header, (ttk.Frame, tk.Frame)):
            self.naming_profiles_button = ttk.Button(
                header,
                text="Profiles...",
                style="Secondary.TButton",
                command=self._show_naming_profiles,
            )
            self.naming_profiles_button.pack(side="right")

    def _folder_label(self, mode: str) -> str:
        normalized = normalize_folder_handling(mode)
        if normalized == FOLDER_ROOT_FLAT:
            return self.FOLDER_ROOT_FLAT_LABEL
        if normalized == FOLDER_KEEP_STRUCTURE:
            return self.FOLDER_KEEP_STRUCTURE_LABEL
        return self.FOLDER_ONE_PER_GAME_LABEL

    def _profile_from_current(self, name: str) -> NamingProfile:
        options = self._current_naming_options()
        return NamingProfile(
            name=name,
            include_title_id=options.include_title_id,
            include_title=options.include_title,
            include_version=options.include_version,
            compact_version=options.compact_version,
            version_prefix=options.version_prefix,
            folder_handling=options.folder_handling,
            component_order=tuple(options.component_order),
            separator=options.separator,
        )

    def _apply_naming_profile(self, profile: NamingProfile) -> None:
        self.include_id_var.set(profile.include_title_id)
        self.include_title_var.set(profile.include_title)
        self.include_version_var.set(profile.include_version)
        self.version_format_var.set(
            self.VERSION_COMPACT if profile.compact_version else self.VERSION_ORIGINAL
        )
        self.version_prefix_var.set(profile.version_prefix)
        self._set_folder_mode(profile.folder_handling)
        self.component_order[:] = list(profile.component_order)
        self._filename_separator = profile.separator
        self.preset_var.set(self.PRESET_CUSTOM)
        self._render_order_editor()
        self._output_setting_changed()
        self._queue_save_preferences()
        self.status_var.set(f"Naming profile applied: {profile.name}")
        self._log("INFO", f"Naming profile applied: {profile.name}")

    @staticmethod
    def _separator_display(value: str) -> str:
        if value == "":
            return "(none)"
        if value == " ":
            return "(space)"
        return value.replace(" ", "·")

    def _show_naming_profiles(self) -> None:
        window = tk.Toplevel(self)
        window.title("Naming profiles")
        window.geometry("780x500")
        window.minsize(650, 420)
        window.transient(self)
        window.grab_set()
        window.configure(bg=COLORS["bg"])

        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Naming profiles", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Save complete filename-builder configurations and switch between them without rescanning. "
                "Bundled profiles are read-only; your own profiles are stored in App Data."
            ),
            style="Subtitle.TLabel",
            wraplength=740,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(content, padding=(14, 0, 0, 0))
        right.pack(side="right", fill="both", expand=True)

        listbox = tk.Listbox(
            left,
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            font=("Segoe UI", 10),
        )
        listbox.pack(fill="both", expand=True)

        detail_var = tk.StringVar(value="Select a profile")
        ttk.Label(
            right,
            textvariable=detail_var,
            style="CardInfo.TLabel",
            wraplength=340,
            justify="left",
        ).pack(anchor="nw", fill="x")

        current: list[tuple[NamingProfile, bool]] = []

        def refresh(select_name: str | None = None) -> None:
            nonlocal current
            current = all_profiles()
            listbox.delete(0, "end")
            selection = 0
            for index, (profile, built_in) in enumerate(current):
                suffix = "  [built-in]" if built_in else ""
                listbox.insert("end", profile.name + suffix)
                if select_name and profile.name.casefold() == select_name.casefold():
                    selection = index
            if current:
                listbox.selection_clear(0, "end")
                listbox.selection_set(selection)
                listbox.see(selection)
                show_selected()

        def selected_pair() -> tuple[NamingProfile, bool] | None:
            selection = listbox.curselection()
            if not selection:
                return None
            index = int(selection[0])
            return current[index] if 0 <= index < len(current) else None

        def show_selected(_event=None) -> None:
            pair = selected_pair()
            if pair is None:
                detail_var.set("Select a profile")
                return
            profile, built_in = pair
            enabled = []
            if profile.include_title_id:
                enabled.append("PPSA")
            if profile.include_title:
                enabled.append("Title")
            if profile.include_version:
                enabled.append("Version")
            order_names = {
                "title_id": "PPSA",
                "title": "Title",
                "version": "Version",
            }
            active_order = [
                order_names[item]
                for item in profile.component_order
                if order_names[item] in enabled
            ]
            detail_var.set(
                f"{profile.name}\n\n"
                f"Type: {'Bundled / read-only' if built_in else 'User profile'}\n"
                f"Components: {', '.join(enabled) or '-'}\n"
                f"Order: {' → '.join(active_order) or '-'}\n"
                f"Version: {'compact' if profile.compact_version else 'original'}"
                f"{' + prefix v' if profile.version_prefix and profile.include_version else ''}\n"
                f"Separator: {self._separator_display(profile.separator)}\n"
                f"Organization: {self._folder_label(profile.folder_handling)}"
            )

        def apply_selected() -> None:
            pair = selected_pair()
            if pair is None:
                return
            self._apply_naming_profile(pair[0])
            window.destroy()

        def save_current() -> None:
            name = simpledialog.askstring(
                "Save naming profile",
                "Profile name:",
                parent=window,
            )
            if name is None:
                return
            name = " ".join(name.strip().split())
            if not name:
                return
            bundled_names = {profile.name.casefold() for profile in BUNDLED_PROFILES}
            if name.casefold() in bundled_names:
                messagebox.showerror(
                    "Naming profiles",
                    "That name is reserved by a bundled profile. Choose another name.",
                    parent=window,
                )
                return
            upsert_user_profile(self._profile_from_current(name))
            self._log("INFO", f"Naming profile saved: {name}")
            refresh(name)

        def delete_selected() -> None:
            pair = selected_pair()
            if pair is None:
                return
            profile, built_in = pair
            if built_in:
                messagebox.showinfo(
                    "Naming profiles",
                    "Bundled profiles cannot be deleted.",
                    parent=window,
                )
                return
            if not messagebox.askyesno(
                "Delete naming profile",
                f"Delete '{profile.name}'?",
                parent=window,
            ):
                return
            if delete_user_profile(profile.name):
                self._log("INFO", f"Naming profile deleted: {profile.name}")
            refresh()

        listbox.bind("<<ListboxSelect>>", show_selected)
        listbox.bind("<Double-1>", lambda _event: apply_selected())

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save current as...", command=save_current).pack(side="left")
        ttk.Button(buttons, text="Delete", command=delete_selected).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Apply profile",
            style="Primary.TButton",
            command=apply_selected,
        ).pack(side="right", padx=(0, 6))
        refresh()

    def _show_options(self) -> None:
        before = set(self.winfo_children())
        super()._show_options()
        created = [
            child
            for child in self.winfo_children()
            if child not in before and isinstance(child, tk.Toplevel)
        ]
        if not created:
            return
        window = created[-1]
        notebook = self._find_notebook(window)
        if notebook is None:
            return

        naming_tab = None
        for tab_id in notebook.tabs():
            if str(notebook.tab(tab_id, "text")).strip().casefold() == "naming":
                naming_tab = notebook.nametowidget(tab_id)
                break
        if naming_tab is None:
            return

        ttk.Separator(naming_tab).pack(fill="x", pady=14)
        ttk.Label(naming_tab, text="Separator & profiles", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            naming_tab,
            text="Choose what is placed between active filename components. Profiles remember this setting too.",
            style="CardMuted.TLabel",
            wraplength=690,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))

        row = ttk.Frame(naming_tab)
        row.pack(fill="x")
        ttk.Label(row, text="Separator", style="CardMuted.TLabel").pack(side="left")
        separator = tk.StringVar(value=self._filename_separator)
        combo = ttk.Combobox(
            row,
            textvariable=separator,
            values=(" - ", "_", " ", ".", " + ", ""),
            width=12,
            style="Performance.TCombobox",
        )
        combo.pack(side="left", padx=(10, 8))

        def apply_separator(_event=None) -> None:
            value = separator.get()[:12]
            if any(char in value for char in '<>:"/\\|?*\x00'):
                messagebox.showerror(
                    "Filename separator",
                    "The separator contains a character that is not valid in Windows filenames.",
                    parent=window,
                )
                separator.set(self._filename_separator)
                return
            self._filename_separator = value
            self.preset_var.set(self.PRESET_CUSTOM)
            self._output_setting_changed()
            self._queue_save_preferences()

        combo.bind("<<ComboboxSelected>>", apply_separator)
        combo.bind("<FocusOut>", apply_separator)
        ttk.Button(row, text="Profiles...", command=self._show_naming_profiles).pack(side="left")
