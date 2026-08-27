from __future__ import annotations

import json
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Mapping

from ..feedback_report import (
    FEEDBACK_CATEGORIES,
    FeedbackReport,
    build_exception_payload,
    collect_diagnostics,
    create_feedback_report,
)
from ..feedback_transport import (
    feedback_endpoint_health,
    queue_feedback_report,
    send_or_queue_feedback,
)


class FeedbackMixin:
    """In-app feedback, privacy-aware diagnostics and queued crash reporting."""

    def __init__(self) -> None:
        self._feedback_window: tk.Toplevel | None = None
        self._handling_callback_exception = False
        super().__init__()

    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return
        end = menubar.index("end")
        if end is None:
            return
        for index in range(int(end) + 1):
            try:
                if menubar.type(index) != "cascade":
                    continue
                if str(menubar.entrycget(index, "label")) != "Help":
                    continue
                menu = self.nametowidget(menubar.entrycget(index, "menu"))
                if not isinstance(menu, tk.Menu):
                    return
                menu.insert_command(0, label="Feedback & Bug Report...", command=self._show_feedback_dialog)
                menu.insert_separator(1)
                return
            except tk.TclError:
                continue

    def _feedback_diagnostics(self) -> dict:
        roots = tuple(getattr(self, "library_roots", ()))
        statuses = []
        root_status = getattr(self, "_root_status", None)
        if callable(root_status):
            for root in roots:
                status = root_status(root)
                if status is not None:
                    statuses.append(status)

        records = tuple(getattr(self, "_all_records", ()))
        result_filter = "ALL"
        variable = getattr(self, "filter_var", None)
        if variable is not None:
            try:
                result_filter = str(variable.get() or "ALL")
            except tk.TclError:
                pass

        return collect_diagnostics(
            root_statuses=statuses,
            record_statuses=(record.view.status for record in records),
            duplicate_group_count=len(getattr(self, "_duplicate_groups", {})),
            scan_total=getattr(self, "last_scan_total", 0),
            cache_hits=getattr(self, "last_cache_hits", 0),
            mkpfs_reads=getattr(self, "last_mkpfs_reads", 0),
            scan_elapsed=getattr(self, "last_scan_elapsed", 0.0),
            worker_count=getattr(self, "last_worker_count", 1),
            scan_active=getattr(self, "_scan_active", False),
            live_watch=getattr(self, "_watch_library", False),
            watch_interval_seconds=getattr(self, "_watch_interval_seconds", 0),
            result_filter=result_filter,
        )

    def _feedback_activity_lines(self) -> tuple[str, ...]:
        activity = getattr(self, "_activity_log", None)
        if activity is None:
            return ()
        try:
            return tuple(activity.tail(80))
        except Exception:
            return ()

    def _make_feedback_report(
        self,
        *,
        category: str,
        summary: str,
        description: str,
        include_diagnostics: bool = True,
        exception: Mapping[str, str] | None = None,
        report_id: str | None = None,
        created_at: str | None = None,
    ) -> FeedbackReport:
        roots = tuple(getattr(self, "library_roots", ()))
        diagnostics = self._feedback_diagnostics() if include_diagnostics else {"included": False}
        return create_feedback_report(
            category=category,
            summary=summary,
            description=description,
            diagnostics=diagnostics,
            roots=roots,
            exception=exception if include_diagnostics else None,
            activity_lines=self._feedback_activity_lines() if include_diagnostics else (),
            report_id=report_id,
            created_at=created_at,
        )

    def _show_feedback_dialog(self, *, prefill_report: FeedbackReport | None = None) -> None:
        existing = self._feedback_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        window = tk.Toplevel(self)
        self._feedback_window = window
        window.title("Feedback & Bug Report")
        window.geometry("760x650")
        window.minsize(640, 540)
        window.transient(self)

        outer = ttk.Frame(window, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Feedback & Bug Report", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Report a bug, request a feature or send a suggestion directly from the application. "
                "Technical data is sanitized before it is queued or submitted."
            ),
            style="Subtitle.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(2, 12))

        form = ttk.Frame(outer)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Category").pack(anchor="w")
        category_var = tk.StringVar(value=prefill_report.category if prefill_report else FEEDBACK_CATEGORIES[0])
        category = ttk.Combobox(
            form,
            textvariable=category_var,
            values=FEEDBACK_CATEGORIES,
            state="readonly",
            width=28,
        )
        category.pack(anchor="w", pady=(3, 10))

        ttk.Label(form, text="Summary").pack(anchor="w")
        summary_var = tk.StringVar(value=prefill_report.summary if prefill_report else "")
        summary_entry = ttk.Entry(form, textvariable=summary_var)
        summary_entry.pack(fill="x", pady=(3, 10))

        ttk.Label(form, text="What happened / what would you like to improve?").pack(anchor="w")
        description = tk.Text(form, height=10, wrap="word")
        description.pack(fill="both", expand=True, pady=(3, 10))
        if prefill_report is not None and prefill_report.description:
            description.insert("1.0", prefill_report.description)

        include_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form,
            text="Include sanitized technical diagnostics and recent activity (recommended)",
            variable=include_var,
        ).pack(anchor="w")
        ttk.Label(
            form,
            text=(
                "Never included: FFPFSC payload contents, credentials or metadata-cache contents. "
                "Configured library paths, user profile locations and usernames are redacted."
            ),
            style="CardMuted.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(3, 8))

        endpoint_state = {"ready": False}
        status_var = tk.StringVar(value="Checking direct feedback channel...")
        ttk.Label(
            form,
            textvariable=status_var,
            style="CardInfo.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        fixed_report_id = prefill_report.report_id if prefill_report else None
        fixed_created_at = prefill_report.created_at if prefill_report else None
        fixed_exception = prefill_report.exception if prefill_report else None

        def build_current() -> FeedbackReport:
            return self._make_feedback_report(
                category=category_var.get(),
                summary=summary_var.get(),
                description=description.get("1.0", "end-1c"),
                include_diagnostics=bool(include_var.get()),
                exception=fixed_exception,
                report_id=fixed_report_id,
                created_at=fixed_created_at,
            )

        def preview() -> None:
            report = build_current()
            self._show_report(
                "Feedback report preview",
                json.dumps(report.payload(), indent=2, ensure_ascii=False, sort_keys=True),
            )

        def save_local() -> None:
            try:
                path = queue_feedback_report(build_current())
            except OSError as exc:
                messagebox.showerror("Feedback report", f"Could not save the report:\n{exc}", parent=window)
                return
            status_var.set(f"Report saved locally: {path.name}")
            self.status_var.set(f"Feedback report queued locally: {path.name}")

        send_button: ttk.Button

        def apply_endpoint_health(health) -> None:
            endpoint_state["ready"] = bool(health.available)
            try:
                send_button.configure(
                    text="Send report" if health.available else "Save report locally",
                    state="normal",
                )
            except tk.TclError:
                return
            status_var.set(health.detail)

        def check_endpoint_async() -> None:
            endpoint_state["ready"] = False
            try:
                send_button.configure(text="Checking...", state="disabled")
            except tk.TclError:
                return
            status_var.set("Checking direct feedback channel...")

            def worker() -> None:
                health = feedback_endpoint_health()
                try:
                    self.after(0, lambda: apply_endpoint_health(health))
                except tk.TclError:
                    pass

            threading.Thread(target=worker, daemon=True, name="ffpfsc-feedback-health").start()

        def send() -> None:
            if not endpoint_state["ready"]:
                save_local()
                return

            report = build_current()
            send_button.configure(state="disabled")
            status_var.set("Saving report locally and attempting secure submission...")

            def worker() -> None:
                result = send_or_queue_feedback(report)

                def done() -> None:
                    try:
                        send_button.configure(state="normal")
                    except tk.TclError:
                        return
                    if result.sent:
                        endpoint_state["ready"] = True
                        send_button.configure(text="Send report")
                        status_var.set("Report sent successfully. Thank you for the feedback.")
                        self.status_var.set(f"Feedback report sent: {report.report_id}")
                        messagebox.showinfo(
                            "Feedback sent",
                            "The report was submitted successfully. Thank you.",
                            parent=window,
                        )
                    else:
                        endpoint_state["ready"] = False
                        send_button.configure(text="Save report locally")
                        queued_name = result.queued_path.name if result.queued_path else report.report_id
                        status_var.set(f"{result.detail} Saved locally as {queued_name}.")
                        self.status_var.set(f"Feedback report queued: {queued_name}")
                        messagebox.showwarning(
                            "Feedback queued",
                            result.detail + "\n\nThe report has been kept safely in the local feedback queue.",
                            parent=window,
                        )

                try:
                    self.after(0, done)
                except tk.TclError:
                    pass

            threading.Thread(target=worker, daemon=True, name="ffpfsc-feedback-submit").start()

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Preview technical data", command=preview).pack(side="left")
        ttk.Button(buttons, text="Save report", command=save_local).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Check connection", command=check_endpoint_async).pack(side="left", padx=(6, 0))
        send_button = ttk.Button(
            buttons,
            text="Checking...",
            command=send,
            style="Primary.TButton",
            state="disabled",
        )
        send_button.pack(side="right")
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right", padx=(0, 6))

        def closed() -> None:
            self._feedback_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", closed)
        summary_entry.focus_set()
        check_endpoint_async()

    def report_callback_exception(self, exc_type, exc_value, tb) -> None:
        """Persist unexpected Tk callback failures and offer one-click reporting."""

        traceback.print_exception(exc_type, exc_value, tb)
        if self._handling_callback_exception:
            return
        self._handling_callback_exception = True
        try:
            roots = tuple(getattr(self, "library_roots", ()))
            exception = build_exception_payload(exc_type, exc_value, tb, roots=roots)
            report = self._make_feedback_report(
                category="Bug report",
                summary=f"Unhandled {getattr(exc_type, '__name__', 'application error')}",
                description=(
                    "An unexpected application error was captured automatically. "
                    "Add any useful context below before sending if desired."
                ),
                include_diagnostics=True,
                exception=exception,
            )
            queued = queue_feedback_report(report)
            try:
                self._log("ERROR", f"Unhandled application exception captured in feedback queue: {queued.name}")
            except Exception:
                pass
            try:
                self.after_idle(lambda: self._show_feedback_dialog(prefill_report=report))
            except tk.TclError:
                pass
        except Exception:
            traceback.print_exc()
        finally:
            self._handling_callback_exception = False
