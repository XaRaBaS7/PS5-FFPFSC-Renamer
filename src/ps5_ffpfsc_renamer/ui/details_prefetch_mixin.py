from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox

from ..details_prefetch import DetailsPrefetchResult, prefetch_game_details


class DetailsPrefetchMixin:
    """Background preloading of selective game-details cache entries."""

    def __init__(self) -> None:
        self._details_prefetch_busy = False
        self._details_prefetch_cancel: threading.Event | None = None
        super().__init__()

    def _prefetch_selected_details(self) -> None:
        records = self._selected_records()
        paths = [record.view.source for record in records]
        if not paths:
            messagebox.showinfo(
                "Preload game details",
                "Select one or more library rows first.",
                parent=self,
            )
            return
        if self._details_prefetch_busy:
            self.status_var.set("Game-details preload is already running")
            return

        worker_setting = str(self.worker_var.get()) if hasattr(self, "worker_var") else "1"
        workers = 1 if worker_setting.startswith("1") else 2
        cancel_event = threading.Event()
        self._details_prefetch_cancel = cancel_event
        self._details_prefetch_busy = True
        self._set_activity(True, f"Preloading game details • {len(paths)} selected")
        self.status_var.set(f"Preloading game details for {len(paths)} selected file(s)...")
        self._log("INFO", f"Game-details preload started: {len(paths)} selected file(s), {workers} worker(s)")

        def progress(done: int, total: int, path: Path, state: str) -> None:
            try:
                self.after(
                    0,
                    lambda: self._details_prefetch_progress(done, total, path, state),
                )
            except Exception:
                pass

        def worker() -> None:
            result = prefetch_game_details(
                paths,
                workers=workers,
                cancel_event=cancel_event,
                progress=progress,
            )
            try:
                self.after(0, lambda: self._details_prefetch_complete(result))
            except Exception:
                pass

        threading.Thread(
            target=worker,
            daemon=True,
            name="ffpfsc-details-prefetch",
        ).start()

    def _details_prefetch_progress(
        self,
        done: int,
        total: int,
        path: Path,
        state: str,
    ) -> None:
        label = {
            "cache": "cache hit",
            "loaded": "loaded",
            "error": "error",
            "cancelled": "cancelled",
        }.get(state, state)
        self.status_var.set(f"Preloading details {done}/{total} • {path.name} • {label}")
        self._set_activity(True, f"Game details {done}/{total} • {label}")

    def _details_prefetch_complete(self, result: DetailsPrefetchResult) -> None:
        self._details_prefetch_busy = False
        self._details_prefetch_cancel = None
        self._set_activity(False, "Details preload complete")

        summary = (
            f"Game-details preload: {result.cached} cache, "
            f"{result.loaded} loaded, {result.failed} failed"
        )
        if result.cancelled:
            self.status_var.set(summary + " • cancelled")
            self._log("WARN", summary + " • cancelled")
            return

        self.status_var.set(summary)
        self._log("WARN" if result.failed else "OK", summary)
        if result.failed and result.failed == result.total:
            preview = "\n".join(
                f"{Path(path).name}: {detail}"
                for path, detail in result.errors[:6]
            )
            messagebox.showwarning(
                "Preload game details",
                "No selected game details could be preloaded.\n\n" + preview,
                parent=self,
            )
