from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ..cache_prune_policy import can_auto_prune_cache, prune_missing_for_roots
from ..settings import AppSettings
from ..theme import COLORS
from ..ui_icons import IconSet


class StartupPreferencesMixin:
    """Startup scan behavior, library browsing preferences and shell icons."""

    def __init__(self) -> None:
        defaults = AppSettings()
        self._autoscan_on_start = defaults.autoscan_on_start
        self._autoscan_on_browse = defaults.autoscan_on_browse
        self._autoscan_on_add_folder = defaults.autoscan_on_add_folder
        self._remember_window_geometry = defaults.remember_window_geometry
        self._show_relative_paths = defaults.show_relative_paths
        self._auto_prune_cache = defaults.auto_prune_cache
        self._ui_icons: IconSet | None = None
        self._startup_scan_pending = False
        self._auto_prune_started = False
        self._auto_prune_probe_pending = False

        super().__init__()

        self.after(650, self._startup_autoscan)
        self.after(900, self._schedule_auto_prune_cache)

    def _icon(self, name: str, size: int = 16, color: str | None = None) -> tk.PhotoImage:
        if self._ui_icons is None:
            self._ui_icons = IconSet(self)
        return self._ui_icons.get(name, size, color)

    def _schedule_auto_prune_cache(self) -> None:
        if self._auto_prune_started or not self._auto_prune_cache or not self.library_roots:
            return
        if self._scan_active or self._startup_scan_pending:
            self.after(750, self._schedule_auto_prune_cache)
            return

        roots = tuple(self.library_roots)
        if any(self._root_status(root) is None for root in roots):
            if self._auto_prune_probe_pending:
                return
            self._auto_prune_probe_pending = True

            def probed() -> None:
                self._auto_prune_probe_pending = False
                # Re-evaluate the current roots after the asynchronous probe.
                # The user may have changed the selection while a slow USB/NAS
                # path was being checked.
                self._schedule_auto_prune_cache()

            self._probe_library_roots_async(callback=probed)
            return

        self._start_auto_prune_cache()

    def _start_auto_prune_cache(self) -> None:
        if self._auto_prune_started or not self._auto_prune_cache:
            return
        if self._scan_active or self._startup_scan_pending:
            self.after(750, self._schedule_auto_prune_cache)
            return

        roots = tuple(self.library_roots)
        if not can_auto_prune_cache(roots, getattr(self, "_root_statuses", {})):
            self._auto_prune_started = True
            try:
                self._log(
                    "CACHE",
                    "Automatic cache prune skipped because not all configured library roots are online.",
                )
            except Exception:
                pass
            return

        self._auto_prune_started = True

        def worker() -> None:
            try:
                removed = prune_missing_for_roots(self.cache, roots)
                error = ""
            except Exception as exc:
                removed = 0
                error = str(exc)

            def done() -> None:
                if error:
                    try:
                        self._log("WARN", f"Automatic cache prune failed: {error}")
                    except Exception:
                        pass
                    return
                if removed and hasattr(self, "cache_entries_var"):
                    try:
                        self.cache_entries_var.set(str(self.cache.entry_count()))
                    except Exception:
                        pass
                try:
                    self._log(
                        "CACHE",
                        f"Automatic cache prune completed: {removed} stale record(s) removed.",
                    )
                except Exception:
                    pass

            try:
                self.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(
            target=worker,
            daemon=True,
            name="ffpfsc-cache-prune",
        ).start()

    def _apply_settings(self, settings: AppSettings) -> None:
        self._autoscan_on_start = settings.autoscan_on_start
        self._autoscan_on_browse = settings.autoscan_on_browse
        self._autoscan_on_add_folder = settings.autoscan_on_add_folder
        self._remember_window_geometry = settings.remember_window_geometry
        self._show_relative_paths = settings.show_relative_paths
        self._auto_prune_cache = settings.auto_prune_cache

        effective = settings
        if not self._remember_window_geometry:
            effective = replace(settings, window_geometry=None)
        super()._apply_settings(effective)

    def _snapshot_settings(self) -> AppSettings:
        base = super()._snapshot_settings()
        return replace(
            base,
            window_geometry=base.window_geometry if self._remember_window_geometry else None,
            autoscan_on_start=self._autoscan_on_start,
            autoscan_on_browse=self._autoscan_on_browse,
            autoscan_on_add_folder=self._autoscan_on_add_folder,
            remember_window_geometry=self._remember_window_geometry,
            show_relative_paths=self._show_relative_paths,
            auto_prune_cache=self._auto_prune_cache,
        )

    def _build_library_controls(self, card: ttk.Frame) -> None:
        super()._build_library_controls(card)
        try:
            self.browse_button.configure(
                image=self._icon("folder", 16, COLORS["accent_hover"]),
                compound="left",
            )
            self.add_folder_button.configure(
                image=self._icon("folder_add", 16, COLORS["accent_hover"]),
                compound="left",
            )
            self.manage_folders_button.configure(
                image=self._icon("folder", 16, COLORS["text_soft"]),
                compound="left",
            )
        except tk.TclError:
            pass

        try:
            self.scan_button.destroy()
        except tk.TclError:
            pass

        actions = ttk.Frame(card, style="Card.TFrame")
        actions.pack(fill="x", pady=(9, 0))

        self.options_button = ttk.Button(
            actions,
            text="Options",
            image=self._icon("options", 16, COLORS["accent_hover"]),
            compound="left",
            style="Secondary.TButton",
            command=self._show_options,
        )
        self.options_button.pack(side="left")

        ttk.Label(
            actions,
            text="Saved folders can auto-scan on startup",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(9, 0))

        self.scan_button = ttk.Button(
            actions,
            text="Scan now  F5",
            image=self._icon("scan", 16, COLORS["text"]),
            compound="left",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.pack(side="right")

    def _set_scan_controls(self, active: bool) -> None:
        super()._set_scan_controls(active)

        # The modern shell moves Options from the central card into the
        # sidebar. The original ttk.Button may already have been destroyed by
        # the time an automatic startup scan toggles the controls. Prefer the
        # live sidebar button and treat a stale Tk widget as a cosmetic no-op.
        button = getattr(self, "_sidebar_options_button", None)
        if button is None:
            button = getattr(self, "options_button", None)
        if button is None:
            return
        try:
            button.configure(state="disabled" if active else "normal")
        except tk.TclError:
            pass

    def _startup_autoscan(self) -> None:
        if self._startup_scan_pending or self._scan_active:
            return
        if not self.library_roots:
            self.status_var.set("Ready — choose a library folder or open Options")
            return
        if not self._autoscan_on_start:
            self.status_var.set(
                f"Restored {len(self.library_roots)} saved folder(s) — press Scan now or F5"
            )
            return

        self._startup_scan_pending = True
        self.status_var.set(
            f"Restored {len(self.library_roots)} saved folder(s) — starting automatic scan..."
        )

        def start() -> None:
            self._startup_scan_pending = False
            if not self._scan_active and self.library_roots:
                self._scan()

        self.after(80, start)

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select FFPFSC folder")
        if not selected:
            return
        self.library_roots = [Path(selected).resolve()]
        self._update_root_summary()
        if self._autoscan_on_browse:
            self.after(40, self._scan)
        else:
            self.status_var.set("Folder selected — press Scan now or F5")

    def _add_folder(self) -> None:
        selected = filedialog.askdirectory(title="Add folder to FFPFSC scan")
        if not selected:
            return
        candidate = Path(selected).resolve()
        existing = {self._root_key(root) for root in self.library_roots}
        if self._root_key(candidate) not in existing:
            self.library_roots.append(candidate)
        self._update_root_summary()
        if self._autoscan_on_add_folder:
            self.after(40, self._scan)
        else:
            self.status_var.set("Folder added — press Scan now or F5")

    def _display_source(self, source: Path) -> str:
        if not self._show_relative_paths:
            return os.path.normpath(os.path.abspath(os.path.expanduser(str(source))))
        return super()._display_source(source)
