from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .gui_v13 import RenamerApp as RenamerAppV13
from .library_watch import LibrarySnapshot, changed_paths, snapshot_library
from .settings import AppSettings
from .theme import COLORS


class RenamerApp(RenamerAppV13):
    """v0.4 Smart Library shell with optional low-impact change watching."""

    def __init__(self) -> None:
        defaults = AppSettings()
        self._watch_library = defaults.watch_library
        self._watch_interval_seconds = defaults.watch_interval_seconds
        self._watch_snapshot: LibrarySnapshot | None = None
        self._watch_after_id: str | None = None
        self._watch_busy = False
        self._watch_button: ttk.Button | None = None
        self._watch_status_var: tk.StringVar | None = None
        super().__init__()
        self.after(1800, self._restart_library_watch)

    # ---------------------------------------------------------- settings
    def _apply_settings(self, settings: AppSettings) -> None:
        self._watch_library = bool(settings.watch_library)
        self._watch_interval_seconds = int(settings.watch_interval_seconds)
        super()._apply_settings(settings)

    def _snapshot_settings(self) -> AppSettings:
        return replace(
            super()._snapshot_settings(),
            watch_library=self._watch_library,
            watch_interval_seconds=self._watch_interval_seconds,
        )

    # ------------------------------------------------------ library card
    def _build_library_controls(self, card: ttk.Frame) -> None:
        super()._build_library_controls(card)
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 0))
        self._watch_status_var = tk.StringVar()
        self._watch_button = ttk.Button(
            row,
            text="Live watch",
            style="Secondary.TButton",
            command=self._toggle_library_watch,
        )
        self._watch_button.pack(side="left")
        ttk.Label(
            row,
            textvariable=self._watch_status_var,
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(8, 0))
        self._refresh_watch_ui()

    def _refresh_watch_ui(self) -> None:
        if self._watch_button is not None:
            self._watch_button.configure(
                text="Live watch: ON" if self._watch_library else "Live watch: OFF"
            )
        if self._watch_status_var is not None:
            if self._watch_library:
                self._watch_status_var.set(f"Checks metadata every {self._watch_interval_seconds}s")
            else:
                self._watch_status_var.set("Optional — disabled to avoid waking HDDs")

    def _toggle_library_watch(self) -> None:
        self._watch_library = not self._watch_library
        self._watch_snapshot = None
        self._refresh_watch_ui()
        self._queue_save_preferences()
        self._restart_library_watch()
        self._log("INFO", f"Live library watch {'enabled' if self._watch_library else 'disabled'}")

    def _update_root_summary(self) -> None:
        super()._update_root_summary()
        self._watch_snapshot = None
        if getattr(self, "_watch_library", False):
            self._restart_library_watch()

    # --------------------------------------------------------- watch loop
    def _cancel_watch_timer(self) -> None:
        if self._watch_after_id is None:
            return
        try:
            self.after_cancel(self._watch_after_id)
        except tk.TclError:
            pass
        self._watch_after_id = None

    def _restart_library_watch(self) -> None:
        self._cancel_watch_timer()
        if not self._watch_library:
            self._refresh_watch_ui()
            return
        delay = max(15, int(self._watch_interval_seconds)) * 1000
        self._watch_after_id = self.after(delay, self._watch_tick)
        self._refresh_watch_ui()

    def _watch_tick(self) -> None:
        self._watch_after_id = None
        if not self._watch_library:
            return
        if self._watch_busy or self._scan_active or not self.library_roots:
            self._restart_library_watch()
            return

        roots = tuple(Path(root) for root in self.library_roots)
        recursive = bool(self.recursive_var.get())
        self._watch_busy = True

        def worker() -> None:
            snapshot = snapshot_library(roots, recursive=recursive)
            try:
                self.after(0, lambda: self._watch_result(snapshot))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True, name="ffpfsc-library-watch").start()

    def _watch_result(self, snapshot: LibrarySnapshot) -> None:
        self._watch_busy = False
        if not self._watch_library:
            return

        if snapshot.unavailable_roots:
            names = ", ".join(snapshot.unavailable_roots[:2])
            extra = "..." if len(snapshot.unavailable_roots) > 2 else ""
            if self._watch_status_var is not None:
                self._watch_status_var.set(f"Waiting for unavailable root: {names}{extra}")
            self._log("WARN", f"Live watch skipped unavailable root(s): {names}{extra}")
            self._restart_library_watch()
            return

        previous = self._watch_snapshot
        self._watch_snapshot = snapshot
        if previous is None:
            if self._watch_status_var is not None:
                self._watch_status_var.set(
                    f"Watching {snapshot.file_count} file(s) every {self._watch_interval_seconds}s"
                )
            self._restart_library_watch()
            return

        changes = changed_paths(previous, snapshot)
        if not changes:
            if self._watch_status_var is not None:
                self._watch_status_var.set(
                    f"Watching {snapshot.file_count} file(s) • no changes"
                )
            self._restart_library_watch()
            return

        preview = ", ".join(Path(path).name for path in changes[:3])
        if len(changes) > 3:
            preview += f" +{len(changes) - 3} more"
        self._log("INFO", f"Live watch detected {len(changes)} changed file(s): {preview}")
        if self._watch_status_var is not None:
            self._watch_status_var.set(f"Change detected • refreshing library")
        if not self._scan_active:
            self.after(60, self._scan)
        self._restart_library_watch()

    # ---------------------------------------------------------- Options
    @staticmethod
    def _find_notebook(widget: tk.Misc) -> ttk.Notebook | None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook):
                return child
            nested = RenamerApp._find_notebook(child)
            if nested is not None:
                return nested
        return None

    def _show_options(self) -> None:
        before = set(self.winfo_children())
        super()._show_options()
        created = [child for child in self.winfo_children() if child not in before and isinstance(child, tk.Toplevel)]
        if not created:
            return
        window = created[-1]
        notebook = self._find_notebook(window)
        if notebook is None:
            return

        automation = ttk.Frame(notebook, padding=16)
        notebook.add(automation, text="Automation")
        ttk.Label(automation, text="Live Library Watch", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            automation,
            text=(
                "Optionally watch selected library roots for new, removed or modified .ffpfsc files. "
                "The watcher only checks filesystem path/size/mtime; MkPFS runs only after a real change triggers a scan."
            ),
            style="CardMuted.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(2, 12))

        enabled = tk.BooleanVar(value=self._watch_library)
        interval = tk.StringVar(value=str(self._watch_interval_seconds))

        def apply_watch() -> None:
            self._watch_library = bool(enabled.get())
            try:
                self._watch_interval_seconds = int(interval.get())
            except ValueError:
                self._watch_interval_seconds = 30
            if self._watch_interval_seconds not in (15, 30, 60, 120):
                self._watch_interval_seconds = 30
            self._watch_snapshot = None
            self._refresh_watch_ui()
            self._queue_save_preferences()
            self._restart_library_watch()

        ttk.Checkbutton(
            automation,
            text="Watch selected folders for FFPFSC changes",
            variable=enabled,
            command=apply_watch,
        ).pack(anchor="w", pady=4)

        interval_row = ttk.Frame(automation)
        interval_row.pack(fill="x", pady=(10, 0))
        ttk.Label(interval_row, text="Check interval", style="CardMuted.TLabel").pack(side="left")
        combo = ttk.Combobox(
            interval_row,
            textvariable=interval,
            values=("15", "30", "60", "120"),
            state="readonly",
            width=8,
            style="Performance.TCombobox",
        )
        combo.pack(side="left", padx=(10, 6))
        ttk.Label(interval_row, text="seconds", style="CardMuted.TLabel").pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _event: apply_watch())

        ttk.Separator(automation).pack(fill="x", pady=16)
        ttk.Label(
            automation,
            text=(
                "Recommendation: leave Live Watch off for archive HDDs that should remain spun down. "
                "Use 30–60 seconds for active SSD/NVMe libraries."
            ),
            style="CardInfo.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w")


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
