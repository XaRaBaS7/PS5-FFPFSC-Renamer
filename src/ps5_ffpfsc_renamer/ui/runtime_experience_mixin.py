from __future__ import annotations

import time
import tkinter as tk
import webbrowser
from tkinter import ttk

from ..rename_plan import PlanStatus
from ..theme import COLORS


class RuntimeExperienceMixin:
    """Live scan feedback plus small non-destructive shell polish."""

    def __init__(self) -> None:
        self._scan_clock_job: str | None = None
        self._scan_clock_started_at: float | None = None
        self._scan_clock_analysis_started_at: float | None = None
        self._scan_clock_completed = 0
        self._scan_clock_total = 0
        self._scan_clock_cache_hits = 0
        self._scan_clock_workers = 1
        self._creator_credit_label: tk.Label | None = None
        self._dialog_polish_bound = False
        super().__init__()

    def _build_ui(self) -> None:
        super()._build_ui()
        self._polish_apply_changes_style()
        self._install_creator_credit()
        self._install_dialog_polish()

    def _polish_apply_changes_style(self) -> None:
        """Keep the final action visibly green, including its disabled cue."""
        try:
            style = ttk.Style(self)
            style.configure(
                "RenamePrimary.TButton",
                background="#38c98b",
                foreground="#07140f",
                borderwidth=0,
                focusthickness=0,
                padding=(17, 9),
                font=("Segoe UI", 10, "bold"),
            )
            style.map(
                "RenamePrimary.TButton",
                background=[
                    ("active", "#55d9a1"),
                    ("pressed", "#2fb77d"),
                    ("disabled", COLORS["success_soft"]),
                ],
                foreground=[("disabled", COLORS["success"])],
            )
        except tk.TclError:
            pass

    def _install_creator_credit(self) -> None:
        """Show the project creator credit at the bottom-right of the app UI."""
        if self._creator_credit_label is not None:
            return
        try:
            header = self._find_main_header()
        except Exception:
            header = None
        if header is None:
            return
        content = header.master
        label = tk.Label(
            content,
            text="Created by XaRaBaS",
            bg=COLORS["bg"],
            fg=COLORS["muted_dark"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["accent_hover"],
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )
        label.bind(
            "<Button-1>",
            lambda _event: webbrowser.open("https://github.com/XaRaBaS7"),
        )
        label.place(relx=1.0, rely=1.0, x=-6, y=-3, anchor="se")
        label.lift()
        self._creator_credit_label = label

    def _install_dialog_polish(self) -> None:
        """Apply small Windows-specific polish when the rename success dialog is mapped."""
        if self._dialog_polish_bound:
            return
        try:
            self.bind_all("<Map>", self._polish_mapped_dialog, add="+")
            self._dialog_polish_bound = True
        except tk.TclError:
            pass

    def _polish_mapped_dialog(self, event) -> None:
        try:
            window = event.widget.winfo_toplevel()
            if window is self or window.title() != "Changes applied":
                return
            if bool(getattr(window, "_ffpfsc_success_polished", False)):
                return
            setattr(window, "_ffpfsc_success_polished", True)
            self.after_idle(lambda current=window: self._polish_success_dialog(current))
        except (AttributeError, tk.TclError):
            return

    def _polish_success_dialog(self, window: tk.Toplevel) -> None:
        """Give the Close CTA enough vertical room and advertise the visible Undo action."""
        try:
            if not window.winfo_exists():
                return
            self._center_modal(window, 520, 330)
        except (AttributeError, tk.TclError):
            return

        def walk(widget: tk.Misc):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        try:
            for candidate in walk(window):
                if not isinstance(candidate, tk.Label):
                    continue
                if str(candidate.cget("text")) == "Ctrl+Z can undo this transaction from Operation History.":
                    candidate.configure(text="Use Undo or Ctrl+Z to restore the previous paths.")
        except tk.TclError:
            pass

    def _refresh_rename_plan_button(self) -> None:
        """Use a concise final-action label while preserving the safe rename path."""
        button = getattr(self, "_rename_plan_button", None)
        if button is None:
            refresh_undo = getattr(self, "_refresh_undo_button", None)
            if callable(refresh_undo):
                refresh_undo()
            return
        try:
            ready_count = sum(1 for item in self.plan if item.status is PlanStatus.READY)
        except Exception:
            ready_count = 0

        scanning = bool(getattr(self, "_scan_active", False))
        if scanning:
            text = "Scanning..."
        elif ready_count:
            text = f"Apply changes ({ready_count})"
        else:
            text = "Apply changes"

        try:
            button.configure(text=text)
            if ready_count <= 0 or scanning:
                button.state(["disabled"])
            else:
                button.state(["!disabled"])
        except tk.TclError:
            pass

        refresh_undo = getattr(self, "_refresh_undo_button", None)
        if callable(refresh_undo):
            refresh_undo()

    @staticmethod
    def _clock_duration(seconds: float) -> str:
        seconds_int = max(0, int(seconds))
        hours, remainder = divmod(seconds_int, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _cancel_scan_clock(self) -> None:
        job = self._scan_clock_job
        self._scan_clock_job = None
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass

    def _start_scan_clock(self) -> None:
        self._cancel_scan_clock()
        self._scan_clock_started_at = time.monotonic()
        self._scan_clock_analysis_started_at = None
        self._scan_clock_completed = 0
        self._scan_clock_total = 0
        self._scan_clock_cache_hits = 0
        self._scan_clock_workers = 1
        self._tick_scan_clock()

    def _tick_scan_clock(self) -> None:
        self._scan_clock_job = None
        if not bool(getattr(self, "_scan_active", False)):
            return
        started = self._scan_clock_started_at
        if started is None:
            return

        now = time.monotonic()
        elapsed = max(0.0, now - started)
        completed = self._scan_clock_completed
        total = self._scan_clock_total
        cache_hits = self._scan_clock_cache_hits
        percent = (completed / total * 100.0) if total else 0.0

        eta = "estimating..."
        active_done = max(0, completed - cache_hits)
        analysis_started = self._scan_clock_analysis_started_at
        if total and completed >= total:
            eta = "00:00"
        elif active_done > 0 and analysis_started is not None:
            active_elapsed = max(0.001, now - analysis_started)
            rate = active_done / active_elapsed
            if rate > 0:
                eta = f"~{self._clock_duration((total - completed) / rate)}"

        overall = getattr(self, "_overall_progress_text", None)
        if overall is not None:
            if total:
                overall.set(
                    f"{completed}/{total} • {percent:.0f}% • "
                    f"elapsed {self._clock_duration(elapsed)} • ETA {eta}"
                )
            else:
                overall.set(f"Working • elapsed {self._clock_duration(elapsed)}")

        try:
            self._refresh_rename_plan_button()
        except Exception:
            pass

        try:
            self._scan_clock_job = self.after(1000, self._tick_scan_clock)
        except tk.TclError:
            self._scan_clock_job = None

    def _scan(self) -> None:
        super()._scan()
        if bool(getattr(self, "_scan_active", False)):
            self._start_scan_clock()

    def _analysis_started(self, total: int, cache_hits: int, misses: int, workers: int) -> None:
        self._scan_clock_total = total
        self._scan_clock_completed = cache_hits
        self._scan_clock_cache_hits = cache_hits
        self._scan_clock_workers = workers
        self._scan_clock_analysis_started_at = time.monotonic()
        super()._analysis_started(total, cache_hits, misses, workers)

    def _progress_update(
        self,
        completed: int,
        total: int,
        started_at: float,
        last_name: str,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        self._scan_clock_completed = completed
        self._scan_clock_total = total
        self._scan_clock_cache_hits = cache_hits
        self._scan_clock_workers = workers
        super()._progress_update(
            completed,
            total,
            started_at,
            last_name,
            workers,
            cache_hits,
            mkpfs_reads,
        )
        self._tick_scan_clock_now()

    def _tick_scan_clock_now(self) -> None:
        """Refresh immediately after progress while retaining the 1-second ticker."""
        if not bool(getattr(self, "_scan_active", False)):
            return
        self._cancel_scan_clock()
        self._tick_scan_clock()

    def _scan_complete(self, *args, **kwargs) -> None:
        self._cancel_scan_clock()
        super()._scan_complete(*args, **kwargs)
        self._refresh_rename_plan_button()

    def _scan_failed(self, detail: str) -> None:
        self._cancel_scan_clock()
        super()._scan_failed(detail)
        self._refresh_rename_plan_button()

    def _scan_cancelled(self, completed: int, total: int) -> None:
        self._cancel_scan_clock()
        super()._scan_cancelled(completed, total)
        self._refresh_rename_plan_button()
