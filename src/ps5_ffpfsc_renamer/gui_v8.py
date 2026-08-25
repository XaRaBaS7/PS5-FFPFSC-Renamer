from __future__ import annotations

from pathlib import Path

from .gui_v7 import RenamerApp as RenamerAppV7
from .settings import load_library_roots, save_library_roots


class RenamerApp(RenamerAppV7):
    """GUI with persistent multi-folder library roots across app restarts."""

    def __init__(self) -> None:
        self._settings_ready = False
        super().__init__()

        self.library_roots = load_library_roots()
        self._settings_ready = True
        self._update_root_summary()

        if self.library_roots:
            count = len(self.library_roots)
            self.status_var.set(
                f"Restored {count} saved scan folder{'s' if count != 1 else ''}. "
                "Press Scan library to refresh them."
            )

    def _update_root_summary(self) -> None:
        super()._update_root_summary()
        if not getattr(self, "_settings_ready", False):
            return
        try:
            save_library_roots(self.library_roots)
        except OSError:
            # Settings persistence is a convenience feature and must never
            # prevent browsing/scanning when AppData is temporarily unwritable.
            pass


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
