from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..game_details import clear_details_cache, details_cache_stats, prune_details_cache
from ..library_view import human_size


class DetailsCacheMaintenanceMixin:
    """Extend Cache Manager with Game Details/artwork cache maintenance."""

    def _show_cache_manager(self) -> None:
        before = set(self.winfo_children())
        super()._show_cache_manager()
        created = [
            child
            for child in self.winfo_children()
            if child not in before and isinstance(child, tk.Toplevel)
        ]
        if not created:
            return
        window = created[-1]
        window.geometry("700x500")
        window.minsize(620, 430)
        frames = [child for child in window.winfo_children() if isinstance(child, ttk.Frame)]
        if not frames:
            return
        frame = frames[0]

        ttk.Separator(frame).pack(fill="x", pady=(18, 12))
        ttk.Label(frame, text="Game details / artwork cache", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "The Details panel caches selectively extracted sce_sys/param.json and icon0.png files. "
                "Prune removes entries whose source FFPFSC was moved, removed or changed."
            ),
            style="CardMuted.TLabel",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))

        stats_var = tk.StringVar()

        def refresh_details_stats() -> None:
            stats = details_cache_stats()
            stats_var.set(
                f"{stats.entries} entries • {stats.valid_entries} valid • "
                f"{stats.stale_entries} stale • {human_size(stats.bytes_on_disk)}"
            )

        ttk.Label(frame, textvariable=stats_var, style="CardInfo.TLabel").pack(anchor="w")
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(8, 0))

        def prune() -> None:
            removed = prune_details_cache()
            refresh_details_stats()
            self._log(
                "CACHE",
                f"Details cache pruned: {removed} stale entr{'y' if removed == 1 else 'ies'} removed",
            )

        def clear() -> None:
            if not messagebox.askyesno(
                "Clear game details cache",
                "Remove all cached param.json and icon0.png files?\n\n"
                "They will be extracted again on demand. Your FFPFSC files are not modified.",
                parent=window,
            ):
                return
            removed = clear_details_cache()
            refresh_details_stats()
            self._log(
                "CACHE",
                f"Details cache cleared: {removed} entr{'y' if removed == 1 else 'ies'} removed",
            )

        ttk.Button(actions, text="Prune stale", command=prune).pack(side="left")
        ttk.Button(actions, text="Clear details cache...", command=clear).pack(side="left", padx=(6, 0))
        refresh_details_stats()
