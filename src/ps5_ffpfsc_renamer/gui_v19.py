from __future__ import annotations

from datetime import datetime
from tkinter import messagebox

from .game_details import migrate_details_cache
from .gui_v18 import RenamerApp as RenamerAppV18
from .operation_history import HistoryError, HistoryTransaction


class RenamerApp(RenamerAppV18):
    """v0.4 keep metadata and details caches hot across Undo too."""

    def _undo_transaction(self, transaction: HistoryTransaction) -> None:
        created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
        if not messagebox.askyesno(
            "Undo rename transaction",
            f"Restore the previous paths for this transaction?\n\n"
            f"{transaction.label}\n{created}\n{transaction.item_count} file(s)\n\n"
            "Undo never overwrites an existing original path.",
            parent=self,
        ):
            return
        try:
            result = self.history.undo(transaction.transaction_id)
        except HistoryError as exc:
            messagebox.showerror("Undo blocked", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Undo failed", str(exc), parent=self)
            return

        mapping = dict(result.restored_pairs)
        migrated_details = 0
        for current_path, restored_path in result.restored_pairs:
            try:
                self.cache.update_path_after_rename(current_path, restored_path)
            except Exception:
                pass
            try:
                if migrate_details_cache(current_path, restored_path):
                    migrated_details += 1
            except Exception:
                pass

        self._update_in_memory_paths(mapping)
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(
            f"Undone: {result.transaction.label} — restored {len(result.restored_pairs)} file(s)"
        )
        self._log(
            "OK",
            f"Undo restored {len(result.restored_pairs)} file(s)"
            + (f" • details cache migrated {migrated_details}" if migrated_details else ""),
        )
        if result.retained_directories:
            messagebox.showwarning(
                "Undo completed with retained folders",
                "The files were restored, but these application-created folders were not empty and were left untouched:\n\n"
                + "\n".join(str(path) for path in result.retained_directories),
                parent=self,
            )


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
