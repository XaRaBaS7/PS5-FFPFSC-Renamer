from __future__ import annotations

from tkinter import messagebox

from .gui_v20 import RenamerApp as RenamerAppV20
from .rename_plan import PlanStatus, RenamePlanItem
from .rename_safety import PreflightReport, VerificationReport, preflight_rename, verify_completed_rename
from .renamer import RenameTransactionError, apply_rename_plan, build_forward_steps


class RenamerApp(RenamerAppV20):
    """v0.4 shell with pre-flight checks and post-rename identity verification."""

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

    def _execute_plan_transaction(
        self,
        items: list[RenamePlanItem],
        *,
        label: str,
    ) -> list[tuple]:
        ready = [item for item in items if item.status is PlanStatus.READY]
        if not ready:
            return []

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
            messagebox.showwarning(
                "Post-rename verification warning",
                "The filesystem rename completed, but one or more identity checks could not be confirmed.\n\n"
                + "\n".join(
                    f"{issue.destination}: {issue.detail}" for issue in verification.issues[:8]
                )
                + "\n\nThe operation is in History and can be undone with Ctrl+Z.",
                parent=self,
            )
        return completed

    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
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

        message = (
            "Apply the current output plan?\n\n"
            + self._preflight_summary(preview_preflight)
            + "\n\nSafety checks:\n"
            "• destinations are checked again immediately before Apply;\n"
            "• the batch is rollback-protected if a later filesystem step fails;\n"
            "• file size + filesystem identity are verified after the rename;\n"
            "• FFPFSC contents are never rewritten or recompressed;\n"
            "• the completed transaction can be undone with Ctrl+Z."
        )
        if not messagebox.askyesno("Confirm rename transaction", message, parent=self):
            return

        try:
            completed = self._execute_plan_transaction(ready, label="Batch rename")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return

        if completed:
            verification = self._last_rename_verification
            verified_text = (
                f"Post-rename verification: {verification.verified_count}/{verification.checked_count} passed."
                if verification is not None
                else "Post-rename verification unavailable."
            )
            messagebox.showinfo(
                "PS5 FFPFSC Renamer",
                f"Completed {len(completed)} file operation(s).\n\n"
                + verified_text
                + "\nNo rescan is required: paths and caches were updated in memory.\n"
                "Press Ctrl+Z if you want to undo this transaction.",
                parent=self,
            )


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
