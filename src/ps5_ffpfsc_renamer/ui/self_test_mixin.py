from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

from ..self_test import SelfTestReport, run_rename_safety_self_test


class SelfTestMixin:
    """Expose the isolated rename-safety self-test in the desktop Tools menu."""

    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return

        try:
            end = menubar.index("end")
        except tk.TclError:
            end = None
        if end is None:
            return

        tools_menu: tk.Menu | None = None
        for index in range(int(end) + 1):
            try:
                if menubar.type(index) == "cascade" and menubar.entrycget(index, "label") == "Tools":
                    menu_name = menubar.entrycget(index, "menu")
                    candidate = self.nametowidget(menu_name)
                    if isinstance(candidate, tk.Menu):
                        tools_menu = candidate
                    break
            except (tk.TclError, KeyError):
                continue

        if tools_menu is None:
            return
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Rename safety self-test...",
            command=self._run_rename_safety_self_test,
        )

    def _run_rename_safety_self_test(self) -> None:
        if getattr(self, "_scan_active", False):
            messagebox.showinfo(
                "Rename safety self-test",
                "Wait for the current library scan to finish before running the self-test.",
                parent=self,
            )
            return

        self.status_var.set("Running isolated rename safety self-test...")
        self._log("INFO", "Rename safety self-test started in an isolated temporary folder")

        def worker() -> None:
            report = run_rename_safety_self_test()
            try:
                self.after(0, lambda: self._finish_rename_safety_self_test(report))
            except tk.TclError:
                pass

        threading.Thread(
            target=worker,
            daemon=True,
            name="ffpfsc-rename-self-test",
        ).start()

    def _finish_rename_safety_self_test(self, report: SelfTestReport) -> None:
        status = "PASS" if report.passed else "FAIL"
        self.status_var.set(
            f"Rename safety self-test: {status} — {report.passed_count}/{len(report.checks)} checks passed"
        )
        self._log(
            "OK" if report.passed else "ERROR",
            f"Rename safety self-test {status}: {report.passed_count}/{len(report.checks)} checks passed in {report.elapsed_seconds:.3f}s",
        )
        for check in report.checks:
            self._log("OK" if check.passed else "ERROR", f"Self-test • {check.name}: {check.detail}")

        if report.passed:
            messagebox.showinfo(
                "Rename safety self-test — PASS",
                report.as_text()
                + "\n\nAll operations were performed only on temporary dummy .ffpfsc files. Your library was not touched.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "Rename safety self-test — FAIL",
                report.as_text()
                + "\n\nNo library files were touched. Review the Activity Log before applying real rename operations.",
                parent=self,
            )
