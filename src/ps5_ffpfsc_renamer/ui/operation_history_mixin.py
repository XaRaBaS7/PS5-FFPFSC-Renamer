from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from ..operation_history import HistoryTransaction


class OperationHistoryMixin:
    """Persistent rename-history UI and latest-transaction undo entry point."""

    def _undo_last_rename(self) -> None:
        transaction = self.history.last_undoable()
        if transaction is None:
            messagebox.showinfo("Undo rename", "There is no rename transaction to undo.", parent=self)
            return
        self._undo_transaction(transaction)

    @staticmethod
    def _transaction_summary(transaction: HistoryTransaction) -> str:
        created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Transaction: {transaction.transaction_id}",
            f"Date: {created}",
            f"Action: {transaction.label}",
            f"Files: {transaction.item_count}",
            f"Status: {'UNDONE' if transaction.is_undone else 'APPLIED'}",
            "",
        ]
        for old, new in transaction.pairs:
            lines.extend((f"From: {old}", f"To:   {new}", ""))
        return "\n".join(lines).rstrip()

    def _show_history_window(self) -> None:
        window = tk.Toplevel(self)
        window.title("Operation history")
        window.transient(self)
        window.geometry("980x520")
        window.minsize(760, 380)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Rename transaction history", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Only the latest applied transaction can be undone. History persists across app restarts.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        tree = ttk.Treeview(
            frame,
            columns=("time", "action", "items", "status"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("time", text="Date")
        tree.heading("action", text="Action")
        tree.heading("items", text="Files")
        tree.heading("status", text="Status")
        tree.column("time", width=170, anchor="w")
        tree.column("action", width=280, anchor="w")
        tree.column("items", width=80, anchor="center")
        tree.column("status", width=110, anchor="center")
        tree.pack(fill="both", expand=True)

        transactions: dict[str, HistoryTransaction] = {}

        def refresh() -> None:
            for row in tree.get_children():
                tree.delete(row)
            transactions.clear()
            for transaction in self.history.recent(100):
                created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
                iid = transaction.transaction_id
                transactions[iid] = transaction
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        created,
                        transaction.label,
                        transaction.item_count,
                        "UNDONE" if transaction.is_undone else "APPLIED",
                    ),
                )

        def selected_transaction() -> HistoryTransaction | None:
            selection = tree.selection()
            return transactions.get(selection[0]) if selection else None

        def show_details() -> None:
            transaction = selected_transaction()
            if transaction is None:
                return
            self._show_report("History details", self._transaction_summary(transaction))

        def undo_selected() -> None:
            transaction = selected_transaction()
            if transaction is None:
                return
            self._undo_transaction(transaction)
            refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Details", command=show_details).pack(side="left")
        ttk.Button(buttons, text="Undo selected", command=undo_selected).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()
