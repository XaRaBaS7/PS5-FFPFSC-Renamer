from __future__ import annotations

from pathlib import Path

from .gui_v17 import RenamerApp as RenamerAppV17
from .library_watch import LibrarySnapshot, diff_snapshots


class RenamerApp(RenamerAppV17):
    """v0.4 richer Live Watch reporting."""

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

        changes = diff_snapshots(previous, snapshot)
        if changes.total == 0:
            if self._watch_status_var is not None:
                self._watch_status_var.set(
                    f"Watching {snapshot.file_count} file(s) • no changes"
                )
            self._restart_library_watch()
            return

        summary = (
            f"Added {len(changes.added)} • Removed {len(changes.removed)} • "
            f"Modified {len(changes.modified)}"
        )
        preview = ", ".join(Path(path).name for path in changes.paths[:3])
        if changes.total > 3:
            preview += f" +{changes.total - 3} more"
        self._log("INFO", f"Live watch: {summary} — {preview}")
        if self._watch_status_var is not None:
            self._watch_status_var.set(f"{summary} • refreshing library")
        if not self._scan_active:
            self.after(60, self._scan)
        self._restart_library_watch()


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
