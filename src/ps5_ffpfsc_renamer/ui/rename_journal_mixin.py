from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, simpledialog

from ..diagnostics import infer_metadata_from_path
from ..rename_plan import PlanStatus, RenamePlanItem
from ..renamer import RenameStep, apply_rename_plan, build_forward_steps


class RenameJournalMixin:
    """Transactional rename journal and in-memory path/cache updates."""

    def _update_in_memory_paths(self, mapping: dict[Path, Path]) -> None:
        if not mapping:
            return
        resolved_mapping = {old.resolve(): new.resolve() for old, new in mapping.items()}

        def mapped(path: Path) -> Path:
            try:
                return resolved_mapping.get(path.resolve(), path)
            except OSError:
                return path

        self.parsed_items = [(mapped(path), metadata) for path, metadata in self.parsed_items]
        self.scan_errors = [(mapped(path), detail) for path, detail in self.scan_errors]
        updated_partial = []
        for item in self.partial_items:
            path, metadata, detail, inference_source, code, friendly = item
            new_path = mapped(path)
            inferred = infer_metadata_from_path(new_path, library_root=self._matching_root(new_path))
            if inferred is not None:
                metadata = inferred.metadata
                inference_source = inferred.source
            updated_partial.append(
                (new_path, metadata, detail, inference_source, code, friendly)
            )
        self.partial_items = updated_partial

    def _finalize_completed_rename(
        self,
        *,
        label: str,
        completed: list[tuple[Path, Path]],
        steps: list[RenameStep],
    ) -> None:
        if not completed:
            return
        for old_path, new_path in completed:
            try:
                self.cache.update_path_after_rename(old_path, new_path)
            except Exception:
                pass

        self._last_rename_undo_available = False
        journal_issue: str | None = None
        try:
            transaction_id = self.history.record(label=label, pairs=completed, steps=steps)
            self._last_rename_undo_available = transaction_id is not None
            if transaction_id is None:
                journal_issue = "No Undo transaction was created for the completed rename."
        except Exception as exc:
            journal_issue = str(exc)

        if journal_issue is not None:
            messagebox.showwarning(
                "Operation history",
                "The rename completed, but its Undo journal could not be saved.\n\n"
                f"{journal_issue}\n\n"
                "The renamed files are valid, but Ctrl+Z is not available for this transaction.",
                parent=self,
            )

        self._update_in_memory_paths(dict(completed))
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        if self._last_rename_undo_available:
            self.status_var.set(
                f"{label}: {len(completed)} file(s) completed — Ctrl+Z can undo the latest transaction; Undo is also available"
            )
        else:
            self.status_var.set(
                f"{label}: {len(completed)} file(s) completed — Undo journal unavailable"
            )

        refresh_undo = getattr(self, "_refresh_undo_button", None)
        if callable(refresh_undo):
            refresh_undo()

    def _execute_plan_transaction(
        self,
        items: list[RenamePlanItem],
        *,
        label: str,
    ) -> list[tuple[Path, Path]]:
        ready = [item for item in items if item.status is PlanStatus.READY]
        if not ready:
            return []
        steps = build_forward_steps(ready)
        completed = apply_rename_plan(ready)
        self._finalize_completed_rename(label=label, completed=completed, steps=steps)
        return completed

    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
            return
        blocked = sum(
            1
            for item in self.plan
            if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}
        )
        message = (
            f"Apply the current output plan to {len(ready)} READY file(s)?\n\n"
            "FFPFSC contents will never be rewritten or recompressed. "
            "The batch is transactional: if a later filesystem operation fails, "
            "earlier completed entries are rolled back.\n\n"
            "When Operation History is saved successfully, the completed transaction can be undone with Ctrl+Z."
        )
        if blocked:
            message += f"\n\n{blocked} blocked row(s) will be left untouched."
        if not messagebox.askyesno("Confirm rename transaction", message, parent=self):
            return
        try:
            completed = self._execute_plan_transaction(ready, label="Batch rename")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return
        if completed:
            undo_text = (
                "Use Undo or Ctrl+Z if you want to restore the previous paths."
                if getattr(self, "_last_rename_undo_available", False)
                else "Undo journal unavailable for this transaction."
            )
            messagebox.showinfo(
                "PS5 FFPFSC Renamer",
                f"Completed {len(completed)} file operation(s).\n\n"
                "No rescan is required: paths and cache were updated in memory.\n"
                + undo_text,
                parent=self,
            )

    def _rename_selected_items(self, items: list[RenamePlanItem]) -> None:
        unique: list[RenamePlanItem] = []
        seen: set[str] = set()
        for item in items:
            key = str(item.source.resolve()).casefold()
            if key not in seen and item.status is PlanStatus.READY:
                seen.add(key)
                unique.append(item)
        if not unique:
            return
        if not messagebox.askyesno(
            "Rename selected files",
            f"Apply the current output plan to {len(unique)} selected READY file(s)?\n\n"
            "The transaction is rollback-protected. Ctrl+Z Undo is available after completion "
            "only if its Operation History entry is saved successfully.",
            parent=self,
        ):
            return
        try:
            self._execute_plan_transaction(unique, label="Selected rename")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)

    def _rename_selected_plan(self, item: RenamePlanItem) -> None:
        if item.status is not PlanStatus.READY:
            return
        if not messagebox.askyesno(
            "Rename selected file",
            f"Apply the current plan only to this file?\n\n"
            f"From:\n{item.source}\n\nTo:\n{item.destination}\n\n"
            "Ctrl+Z Undo is available after completion only if its Operation History entry is saved successfully.",
            parent=self,
        ):
            return
        try:
            self._execute_plan_transaction([item], label="Single rename")
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)

    def _manual_rename(self, source: Path) -> None:
        if not source.exists():
            messagebox.showerror("Rename", "The selected file no longer exists.", parent=self)
            return
        entered = simpledialog.askstring(
            "Rename file manually",
            "New filename:",
            initialvalue=source.name,
            parent=self,
        )
        if entered is None:
            return
        name = entered.strip()
        if not name:
            return
        if not name.lower().endswith(".ffpfsc"):
            name += ".ffpfsc"
        if Path(name).name != name or any(char in name for char in '<>:"/\\|?*'):
            messagebox.showerror(
                "Invalid filename",
                "Use only a filename, without path characters or Windows-invalid characters.",
                parent=self,
            )
            return
        destination = source.with_name(name)
        if destination == source:
            return
        if destination.exists():
            messagebox.showerror("Rename", "A file with that name already exists.", parent=self)
            return

        step = RenameStep("rename_file", source, destination)
        try:
            source.rename(destination)
        except OSError as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return
        self._finalize_completed_rename(
            label="Manual rename",
            completed=[(source, destination)],
            steps=[step],
        )
