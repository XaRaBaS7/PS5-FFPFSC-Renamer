from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .game_details import details_cache_stats, migrate_details_cache
from .gui_v15 import RenamerApp as RenamerAppV15
from .library_stats import summarize_library
from .library_view import human_size
from .renamer import RenameStep
from .theme import COLORS


class RenamerApp(RenamerAppV15):
    """v0.4 library insights and rename-aware details cache migration."""

    # -------------------------------------------------------------- menus
    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return
        end = menubar.index("end")
        if end is None:
            return
        tools_menu = None
        for index in range(int(end) + 1):
            try:
                if menubar.type(index) != "cascade":
                    continue
                if str(menubar.entrycget(index, "label")) != "Tools":
                    continue
                tools_menu = self.nametowidget(menubar.entrycget(index, "menu"))
                break
            except tk.TclError:
                continue
        if not isinstance(tools_menu, tk.Menu):
            return
        # Keep statistics close to the existing health report. It is a pure
        # in-memory view and never reads/re-writes an FFPFSC payload.
        try:
            tools_menu.insert_command(
                5,
                label="Library statistics...",
                command=self._show_library_statistics,
            )
        except tk.TclError:
            tools_menu.add_command(
                label="Library statistics...",
                command=self._show_library_statistics,
            )

    # ------------------------------------------------------- rename cache
    def _finalize_completed_rename(
        self,
        *,
        label: str,
        completed: list[tuple],
        steps: list[RenameStep],
    ) -> None:
        super()._finalize_completed_rename(label=label, completed=completed, steps=steps)
        migrated = 0
        for old_path, new_path in completed:
            try:
                if migrate_details_cache(old_path, new_path):
                    migrated += 1
            except Exception:
                continue
        if migrated:
            self._log(
                "CACHE",
                f"Migrated game-details cache for {migrated} renamed file(s)",
            )

    # ---------------------------------------------------------- statistics
    def _show_library_statistics(self) -> None:
        records = list(getattr(self, "_all_records", []))
        stats = summarize_library(record.view for record in records)
        details_stats = details_cache_stats()

        window = tk.Toplevel(self)
        window.title("Library Statistics")
        window.geometry("900x650")
        window.minsize(760, 540)
        window.transient(self)
        window.configure(bg=COLORS["bg"])

        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Library Statistics", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Instant summary from the current in-memory scan — no additional MkPFS reads.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        cards = ttk.Frame(outer)
        cards.pack(fill="x")
        card_data = (
            ("Files", str(stats.total_files), "current results"),
            ("Library size", human_size(stats.total_size), f"{stats.known_size_files} sized files"),
            ("Unique Title IDs", str(stats.unique_title_ids), "verified / displayed IDs"),
            (
                "Duplicates",
                str(stats.duplicate_groups),
                f"{stats.duplicate_files} files in duplicate groups",
            ),
        )
        for column, (title, value, note) in enumerate(card_data):
            cards.columnconfigure(column, weight=1, uniform="stats")
            card = ttk.Frame(cards, style="Card.TFrame", padding=12)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 0))
            ttk.Label(card, text=value, style="StatNumber.TLabel").pack(anchor="w")
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, text=note, style="CardMuted.TLabel").pack(anchor="w")

        info = ttk.Frame(outer)
        info.pack(fill="x", pady=(12, 8))
        ttk.Label(
            info,
            text=f"Average known file size: {human_size(stats.average_size)}",
            style="CardInfo.TLabel",
        ).pack(side="left")
        ttk.Label(
            info,
            text=(
                f"Details cache: {details_stats.valid_entries}/{details_stats.entries} valid • "
                f"{human_size(details_stats.bytes_on_disk)}"
            ),
            style="CardInfo.TLabel",
        ).pack(side="right")

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)

        statuses = ttk.Frame(panes, style="Card.TFrame", padding=10)
        largest = ttk.Frame(panes, style="Card.TFrame", padding=10)
        panes.add(statuses, weight=1)
        panes.add(largest, weight=2)

        ttk.Label(statuses, text="Status distribution", style="CardTitle.TLabel").pack(anchor="w")
        status_tree = ttk.Treeview(
            statuses,
            columns=("status", "count", "share"),
            show="headings",
            height=12,
            style="Library.Treeview",
        )
        status_tree.heading("status", text="Status")
        status_tree.heading("count", text="Count")
        status_tree.heading("share", text="Share")
        status_tree.column("status", width=120, anchor="w")
        status_tree.column("count", width=70, anchor="e")
        status_tree.column("share", width=75, anchor="e")
        status_tree.pack(fill="both", expand=True, pady=(8, 0))
        for status, count in stats.status_counts:
            share = (count / stats.total_files * 100.0) if stats.total_files else 0.0
            status_tree.insert("", "end", values=(status, count, f"{share:.1f}%"))

        ttk.Label(largest, text="Largest games", style="CardTitle.TLabel").pack(anchor="w")
        largest_tree = ttk.Treeview(
            largest,
            columns=("title", "title_id", "size", "status"),
            show="headings",
            height=12,
            style="Library.Treeview",
        )
        largest_tree.heading("title", text="Title")
        largest_tree.heading("title_id", text="Title ID")
        largest_tree.heading("size", text="Size")
        largest_tree.heading("status", text="Status")
        largest_tree.column("title", width=280, anchor="w")
        largest_tree.column("title_id", width=105, anchor="w")
        largest_tree.column("size", width=95, anchor="e")
        largest_tree.column("status", width=90, anchor="w")
        largest_tree.pack(fill="both", expand=True, pady=(8, 0))
        for row in stats.largest:
            largest_tree.insert(
                "",
                "end",
                values=(row.title, row.title_id, human_size(row.size), row.status),
            )

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        unavailable = tuple(getattr(self, "_last_unavailable_roots", ()))
        ttk.Label(
            footer,
            text=(
                f"Unavailable roots: {len(unavailable)}"
                if unavailable
                else "All selected roots available during the last scan"
            ),
            style="CardMuted.TLabel",
        ).pack(side="left")
        ttk.Button(footer, text="Close", command=window.destroy).pack(side="right")


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
