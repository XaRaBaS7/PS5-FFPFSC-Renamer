from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..library_view import human_size


class MetadataCacheManagerMixin:
    """Metadata-cache maintenance window extracted from the legacy v0.3 shell."""

    def _show_cache_manager(self) -> None:
        window = tk.Toplevel(self)
        window.title("Cache Manager")
        window.transient(self)
        window.geometry("650x330")
        window.minsize(560, 300)

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Metadata cache", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Verified metadata and unchanged MkPFS failures are stored separately in the same SQLite database.",
            style="CardMuted.TLabel",
            wraplength=600,
        ).pack(anchor="w", pady=(2, 10))

        info_var = tk.StringVar()
        path_var = tk.StringVar(value=str(self.cache.db_path))
        ttk.Label(frame, textvariable=info_var, style="Card.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(frame, textvariable=path_var, style="CardMuted.TLabel", wraplength=600).pack(anchor="w")

        def refresh() -> None:
            stats = self.cache.stats()
            info_var.set(
                f"Verified: {stats.entries}     Remembered errors: {stats.failed_entries}     "
                f"Disk: {human_size(stats.database_bytes)}"
            )
            self.cache_entries_var.set(str(stats.entries))

        def prune() -> None:
            if self._scan_active:
                messagebox.showinfo(
                    "Cache Manager",
                    "Wait for the current scan to finish first.",
                    parent=window,
                )
                return
            try:
                removed = self.cache.prune_missing()
            except Exception as exc:
                messagebox.showerror("Cache Manager", str(exc), parent=window)
                return
            refresh()
            messagebox.showinfo(
                "Cache Manager",
                f"Removed {removed} stale cache record(s).",
                parent=window,
            )

        def compact() -> None:
            if self._scan_active:
                messagebox.showinfo(
                    "Cache Manager",
                    "Wait for the current scan to finish first.",
                    parent=window,
                )
                return
            try:
                self.cache.vacuum()
            except Exception as exc:
                messagebox.showerror("Cache Manager", str(exc), parent=window)
                return
            refresh()
            messagebox.showinfo("Cache Manager", "SQLite cache compacted.", parent=window)

        def clear_all() -> None:
            if self._scan_active:
                return
            if not messagebox.askyesno(
                "Clear metadata cache",
                "Delete all verified metadata and remembered error cache entries?\n\n"
                "The next scan will ask MkPFS to inspect every file again.",
                parent=window,
            ):
                return
            self.cache.clear()
            self.cached_var.set("0")
            refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Prune missing", command=prune).pack(side="left")
        ttk.Button(buttons, text="Compact DB", command=compact).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Clear all...", command=clear_all).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons,
            text="Open folder",
            command=lambda: self._open_folder(self.cache.db_path),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()
