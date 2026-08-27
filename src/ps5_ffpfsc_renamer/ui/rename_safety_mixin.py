from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..naming import (
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    effective_folder_handling,
)
from ..rename_plan import PlanStatus, RenamePlanItem
from ..rename_safety import (
    PreflightReport,
    VerificationReport,
    preflight_rename,
    verify_completed_rename,
)
from ..renamer import RenameTransactionError, apply_rename_plan, build_forward_steps
from ..theme import COLORS


class RenameSafetyMixin:
    """Fresh pre-flight and post-rename identity verification for the desktop UI."""

    def __init__(self) -> None:
        self._last_rename_verification: VerificationReport | None = None
        super().__init__()

    @staticmethod
    def _preflight_summary(report: PreflightReport) -> str:
        lines = [
            f"READY files: {report.ready_count}",
            f"Data represented: {report.total_gib:.2f} GiB",
            f"File path changes: {report.file_renames}",
            f"Folders to create: {report.directories_created}",
            f"Folders to rename: {report.directories_renamed}",
        ]
        if report.blocked_count:
            lines.append(f"Blocked rows left untouched: {report.blocked_count}")
        if report.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"• {warning}" for warning in report.warnings[:5])
        return "\n".join(lines)

    def _organization_confirmation_text(self) -> tuple[str, str, str | None]:
        options = self._current_naming_options()
        mode = effective_folder_handling(options)
        roots = tuple(options.library_roots)
        root_text = roots[0] if len(roots) == 1 else None

        if mode == FOLDER_ROOT_FLAT:
            description = (
                "Every READY .ffpfsc will end directly in its selected library root. "
                "No per-game folders will be created or renamed."
            )
            return "All files in library root", description, root_text
        if mode == FOLDER_KEEP_STRUCTURE:
            description = (
                "Every READY .ffpfsc stays in its current folder. Only the filename changes; "
                "no folder is created, moved or renamed."
            )
            return "Keep current structure", description, root_text
        if mode == FOLDER_ONE_PER_GAME:
            description = (
                "Every READY .ffpfsc will end in one dedicated game folder directly under its library root. "
                "Safe existing game folders may be renamed instead of recreated."
            )
            return "One folder per game", description, root_text
        return "Library organization", "Apply the current library organization plan.", root_text

    def _center_modal(self, window: tk.Toplevel, width: int, height: int) -> None:
        self.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _confirm_rename_dialog(
        self,
        report: PreflightReport,
        ready: list[RenamePlanItem],
    ) -> bool:
        result = {"confirmed": False}
        window = tk.Toplevel(self)
        window.title("Review changes")
        window.configure(bg=COLORS["bg"])
        window.transient(self)
        window.resizable(False, False)
        self._center_modal(window, 690, 510)

        outer = tk.Frame(window, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=22, pady=20)

        tk.Label(
            outer,
            text="Review changes",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            outer,
            text="Nothing is changed until you confirm this plan.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        mode_title, mode_description, root_text = self._organization_confirmation_text()
        mode_box = tk.Frame(
            outer,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["accent"],
        )
        mode_box.pack(fill="x")
        tk.Label(
            mode_box,
            text="LIBRARY ORGANIZATION",
            bg=COLORS["panel"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 1))
        tk.Label(
            mode_box,
            text=mode_title,
            bg=COLORS["panel"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12)
        tk.Label(
            mode_box,
            text=mode_description,
            bg=COLORS["panel"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=635,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(3, 4))
        if root_text:
            tk.Label(
                mode_box,
                text=f"Library root:  {root_text}",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Consolas", 8),
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 9))
        else:
            tk.Label(
                mode_box,
                text="Each file stays associated with its own selected library root.",
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8),
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 9))

        stats = tk.Frame(outer, bg=COLORS["bg"])
        stats.pack(fill="x", pady=(12, 0))
        for column in range(4):
            stats.grid_columnconfigure(column, weight=1, uniform="rename_stats")

        stat_values = (
            (report.ready_count, "FILES READY"),
            (report.file_renames, "PATH CHANGES"),
            (report.directories_created, "NEW FOLDERS"),
            (report.directories_renamed, "FOLDERS RENAMED"),
        )
        for column, (value, label) in enumerate(stat_values):
            box = tk.Frame(
                stats,
                bg=COLORS["surface"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            box.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 4, 0 if column == 3 else 4),
            )
            tk.Label(
                box,
                text=str(value),
                bg=COLORS["surface"],
                fg=COLORS["text"],
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", padx=10, pady=(7, 0))
            tk.Label(
                box,
                text=label,
                bg=COLORS["surface"],
                fg=COLORS["muted"],
                font=("Segoe UI", 7, "bold"),
            ).pack(anchor="w", padx=10, pady=(0, 7))

        moved_count = sum(
            1
            for item in ready
            if item.source.parent.resolve() != item.destination.parent.resolve()
        )
        detail_parts = [f"{report.total_gib:.2f} GiB represented"]
        if moved_count:
            detail_parts.append(f"{moved_count} file(s) change folder location")
        if report.blocked_count:
            detail_parts.append(f"{report.blocked_count} blocked row(s) stay untouched")
        tk.Label(
            outer,
            text="  •  ".join(detail_parts),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

        safety_box = tk.Frame(
            outer,
            bg=COLORS["success_soft"],
            highlightthickness=1,
            highlightbackground=COLORS["success"],
        )
        safety_box.pack(fill="x", pady=(12, 0))
        tk.Label(
            safety_box,
            text="✓  FFPFSC contents are never rewritten or recompressed.",
            bg=COLORS["success_soft"],
            fg=COLORS["success"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=11, pady=(8, 2))
        tk.Label(
            safety_box,
            text=(
                "Destinations are checked again immediately before Apply. The batch is rollback-protected, "
                "file identity is verified afterwards, and Ctrl+Z Undo is recorded when History is saved."
            ),
            bg=COLORS["success_soft"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=630,
            anchor="w",
        ).pack(fill="x", padx=11, pady=(0, 8))

        if report.warnings:
            warning_text = " • ".join(report.warnings[:3])
            tk.Label(
                outer,
                text=f"Warning: {warning_text}",
                bg=COLORS["bg"],
                fg=COLORS["warning"],
                font=("Segoe UI", 8),
                wraplength=640,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(7, 0))

        buttons = tk.Frame(outer, bg=COLORS["bg"])
        buttons.pack(side="bottom", fill="x", pady=(15, 0))

        def cancel() -> None:
            result["confirmed"] = False
            window.destroy()

        def confirm() -> None:
            result["confirmed"] = True
            window.destroy()

        ttk.Button(
            buttons,
            text="Cancel",
            style="Secondary.TButton",
            command=cancel,
        ).pack(side="right")
        ttk.Button(
            buttons,
            text=f"Apply {report.ready_count} changes",
            style="RenamePrimary.TButton",
            command=confirm,
        ).pack(side="right", padx=(0, 8))

        window.protocol("WM_DELETE_WINDOW", cancel)
        window.bind("<Escape>", lambda _event: cancel())
        window.bind("<Return>", lambda _event: confirm())
        window.grab_set()
        window.focus_force()
        window.wait_window()
        return bool(result["confirmed"])

    def _show_rename_completed_dialog(self, completed_count: int) -> None:
        verification = self._last_rename_verification
        verified_text = (
            f"Verified {verification.verified_count}/{verification.checked_count} destination file identities."
            if verification is not None
            else "Post-rename verification was unavailable."
        )
        undo_text = (
            "Ctrl+Z can undo this transaction from Operation History."
            if getattr(self, "_last_rename_undo_available", False)
            else "No Undo journal is available for this transaction."
        )

        window = tk.Toplevel(self)
        window.title("Changes applied")
        window.configure(bg=COLORS["bg"])
        window.transient(self)
        window.resizable(False, False)
        self._center_modal(window, 520, 285)

        outer = tk.Frame(window, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=22, pady=20)
        tk.Label(
            outer,
            text="✓",
            bg=COLORS["bg"],
            fg=COLORS["success"],
            font=("Segoe UI", 26, "bold"),
        ).pack(anchor="w")
        tk.Label(
            outer,
            text="Changes applied successfully",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            outer,
            text=f"Completed {completed_count} file operation(s).",
            bg=COLORS["bg"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(3, 12))

        info = tk.Frame(
            outer,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        info.pack(fill="x")
        tk.Label(
            info,
            text=verified_text,
            bg=COLORS["panel"],
            fg=COLORS["success"] if verification and verification.passed else COLORS["text_soft"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=11, pady=(9, 2))
        tk.Label(
            info,
            text="Paths and caches were updated in memory; no rescan is required.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=11)
        tk.Label(
            info,
            text=undo_text,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=11, pady=(2, 9))

        ttk.Button(
            outer,
            text="Close",
            style="Primary.TButton",
            command=window.destroy,
        ).pack(side="bottom", anchor="e", pady=(14, 0))
        window.bind("<Escape>", lambda _event: window.destroy())
        window.bind("<Return>", lambda _event: window.destroy())
        window.grab_set()
        window.focus_force()
        window.wait_window()

    def _require_fresh_scan_view(self) -> None:
        if getattr(self, "_scan_view_stale", False):
            raise RenameTransactionError(
                "The current library view was restored from the previous successful scan because "
                "the latest scan did not complete. Run Scan library successfully before applying "
                "an automatic rename plan."
            )

    def _execute_plan_transaction(
        self,
        items: list[RenamePlanItem],
        *,
        label: str,
    ) -> list[tuple]:
        ready = [item for item in items if item.status is PlanStatus.READY]
        if not ready:
            return []
        self._require_fresh_scan_view()

        # Re-run preflight immediately before filesystem mutation. This catches
        # a late destination collision that appeared after the UI preview.
        preflight = preflight_rename(ready)
        if not preflight.can_apply:
            detail = "\n".join(preflight.errors[:8]) or "Pre-flight did not approve this rename."
            self._log("ERROR", f"Rename pre-flight blocked {label}: {detail}")
            raise RenameTransactionError(f"Rename pre-flight blocked the operation:\n\n{detail}")

        self._log(
            "INFO",
            f"Rename pre-flight OK • {preflight.ready_count} file(s) • {preflight.total_gib:.2f} GiB • "
            f"create folders {preflight.directories_created} • rename folders {preflight.directories_renamed}",
        )

        steps = build_forward_steps(ready)
        completed = apply_rename_plan(ready)
        verification = verify_completed_rename(preflight, completed)
        self._last_rename_verification = verification

        self._finalize_completed_rename(label=label, completed=completed, steps=steps)

        if verification.passed:
            self._log(
                "OK",
                f"Post-rename verification passed • {verification.verified_count}/{verification.checked_count} "
                "destination file identities preserved",
            )
        else:
            details = "; ".join(issue.detail for issue in verification.issues[:5])
            self._log("ERROR", f"Post-rename verification warning: {details}")
            undo_note = (
                "The operation is in History and can be undone with Ctrl+Z."
                if getattr(self, "_last_rename_undo_available", False)
                else "No Undo journal is available for this transaction."
            )
            messagebox.showwarning(
                "Post-rename verification warning",
                "The filesystem rename completed, but one or more identity checks could not be confirmed.\n\n"
                + "\n".join(
                    f"{issue.destination}: {issue.detail}" for issue in verification.issues[:8]
                )
                + "\n\n"
                + undo_note,
                parent=self,
            )
        return completed

    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
            return
        if getattr(self, "_scan_view_stale", False):
            messagebox.showwarning(
                "Scan required",
                "The displayed results come from the previous successful scan because the latest scan "
                "did not complete. Complete a fresh scan before applying an automatic rename plan.",
                parent=self,
            )
            return

        preview_preflight = preflight_rename(self.plan)
        if preview_preflight.errors:
            detail = "\n".join(preview_preflight.errors[:8])
            messagebox.showerror(
                "Rename pre-flight blocked",
                "The rename preview is no longer safe to apply:\n\n" + detail + "\n\nRefresh the library and review the plan.",
                parent=self,
            )
            return

        if not self._confirm_rename_dialog(preview_preflight, ready):
            return

        try:
            completed = self._execute_plan_transaction(ready, label="Batch rename")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return

        if completed:
            self._show_rename_completed_dialog(len(completed))
