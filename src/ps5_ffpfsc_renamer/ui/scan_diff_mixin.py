from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import tkinter as tk

from ..library_view import human_size
from ..scan_snapshot import (
    ScanDiff,
    ScanSnapshot,
    build_scan_snapshot,
    compare_scan_snapshots,
    load_scan_snapshot,
    migrate_snapshot_paths,
    save_scan_snapshot,
)
from ..scan_snapshot_preserve import carry_forward_preserved_entries


class ScanDiffMixin:
    """Persist a lightweight successful-scan baseline and report library changes."""

    def __init__(self) -> None:
        self._scan_snapshot: ScanSnapshot | None = load_scan_snapshot()
        self._last_scan_diff: ScanDiff | None = None
        super().__init__()

    def _build_product_menu(self) -> None:
        super()._build_product_menu()
        menubar = getattr(self, "_product_menu", None)
        if not isinstance(menubar, tk.Menu):
            return

        def cascade(label: str) -> tk.Menu | None:
            end = menubar.index("end")
            if end is None:
                return None
            for index in range(int(end) + 1):
                try:
                    if menubar.type(index) != "cascade":
                        continue
                    if str(menubar.entrycget(index, "label")) != label:
                        continue
                    menu = self.nametowidget(menubar.entrycget(index, "menu"))
                    return menu if isinstance(menu, tk.Menu) else None
                except tk.TclError:
                    continue
            return None

        tools_menu = cascade("Tools")
        if tools_menu is not None:
            try:
                tools_menu.insert_command(
                    5,
                    label="Changes since previous scan...",
                    command=self._show_scan_changes,
                )
            except tk.TclError:
                tools_menu.add_command(
                    label="Changes since previous scan...",
                    command=self._show_scan_changes,
                )

        edit_menu = cascade("Edit")
        if edit_menu is not None:
            edit_menu.add_separator()
            edit_menu.add_command(label="Select added rows", command=self._select_added_rows)
            edit_menu.add_command(label="Select changed rows", command=self._select_changed_rows)
            edit_menu.add_command(
                label="Select added + changed rows",
                command=self._select_all_scan_change_rows,
            )

    def _select_scan_change_rows(self, states: set[str], *, label: str) -> int:
        normalized = {state.strip().upper() for state in states if state.strip()}
        allowed = {"ADDED", "CHANGED"}
        if not normalized or not normalized <= allowed:
            raise ValueError("Scan change selection supports ADDED and CHANGED only")

        self.search_var.set("")
        self.filter_var.set(next(iter(normalized)) if len(normalized) == 1 else "ALL")
        self._render_records()

        rows = tuple(
            row
            for row, record in self._row_records.items()
            if record.view.change.upper() in normalized
        )
        if rows:
            self.tree.selection_set(*rows)
            self.tree.focus(rows[0])
            self.tree.see(rows[0])
        self.status_var.set(f"{len(rows)} {label} selected")
        return len(rows)

    def _select_added_rows(self) -> int:
        return self._select_scan_change_rows({"ADDED"}, label="added row(s)")

    def _select_changed_rows(self) -> int:
        return self._select_scan_change_rows({"CHANGED"}, label="changed row(s)")

    def _select_all_scan_change_rows(self) -> int:
        return self._select_scan_change_rows(
            {"ADDED", "CHANGED"},
            label="added/changed row(s)",
        )

    def _scan_complete(
        self,
        parsed,
        errors,
        total: int,
        started_at: float,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        super()._scan_complete(
            parsed,
            errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )

        records = list(getattr(self, "_all_records", []))
        current = build_scan_snapshot(
            (record.view for record in records),
            roots=getattr(self, "library_roots", ()),
            file_states=getattr(self, "_last_scan_file_states", {}),
        )
        previous = self._scan_snapshot
        if previous is not None:
            current = carry_forward_preserved_entries(
                previous,
                current,
                getattr(self, "_offline_preserved_paths", ()),
            )
        self._last_scan_diff = (
            compare_scan_snapshots(previous, current) if previous is not None else None
        )
        self._scan_snapshot = current

        try:
            save_scan_snapshot(current)
        except OSError as exc:
            self._log("WARN", f"Could not save library scan baseline: {exc}")

        diff = self._last_scan_diff
        if diff is None:
            self._log("INFO", f"Library change baseline created with {len(current.entries)} file(s)")
            return

        self._apply_scan_change_markers(diff)
        summary = (
            f"Library changes: +{len(diff.added)} added, -{len(diff.removed)} removed, "
            f"{len(diff.changed)} changed"
        )
        if diff.roots_changed:
            summary += " • selected roots changed"
        self._log("INFO" if not diff.has_changes else "WARN", summary)
        if diff.has_changes:
            self.progress_note_var.set(self.progress_note_var.get() + " " + summary + ".")

    def _apply_scan_change_markers(self, diff: ScanDiff) -> None:
        added = {entry.path.casefold() for entry in diff.added}
        changed = {entry.after.path.casefold() for entry in diff.changed}
        touched = False
        for record in getattr(self, "_all_records", []):
            key = str(record.view.source).casefold()
            change = "ADDED" if key in added else "CHANGED" if key in changed else ""
            if record.view.change != change:
                record.view = replace(record.view, change=change)
                touched = True
        if touched:
            self._render_records()

    def _finalize_completed_rename(self, *, label: str, completed: list[tuple], steps) -> None:
        super()._finalize_completed_rename(label=label, completed=completed, steps=steps)
        if not completed:
            return

        # A rename performed by this app is intentional, not a library change.
        # Migrate both the persisted baseline and the stat snapshot so the next
        # scan does not report a false removed+added pair.
        if self._scan_snapshot is not None:
            self._scan_snapshot = migrate_snapshot_paths(self._scan_snapshot, completed)
            try:
                save_scan_snapshot(self._scan_snapshot)
            except OSError as exc:
                self._log("WARN", f"Could not migrate library scan baseline after rename: {exc}")

        states = getattr(self, "_last_scan_file_states", None)
        if isinstance(states, dict):
            for old_path, new_path in completed:
                state = states.pop(old_path, None)
                if state is None:
                    old_key = str(old_path).casefold()
                    matching = next(
                        (key for key in list(states) if str(key).casefold() == old_key),
                        None,
                    )
                    if matching is not None:
                        state = states.pop(matching)
                if state is not None:
                    states[Path(new_path)] = state

    @staticmethod
    def _format_snapshot_time(timestamp: int) -> str:
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return str(timestamp)

    @staticmethod
    def _entry_line(prefix: str, entry) -> str:
        title = entry.title if entry.title and entry.title != "-" else entry.path
        title_id = f" [{entry.title_id}]" if entry.title_id and entry.title_id != "-" else ""
        return f"{prefix} {title}{title_id} • {human_size(entry.size)} • {entry.status}\n    {entry.path}"

    def _show_scan_changes(self) -> None:
        diff = self._last_scan_diff
        if diff is None:
            if self._scan_snapshot is None:
                text = (
                    "No successful scan baseline exists yet.\n\n"
                    "Scan the library once; subsequent scans will report added, removed and changed FFPFSC files."
                )
            else:
                text = (
                    "A scan baseline exists, but this application session has not completed a comparison scan yet.\n\n"
                    "Run Scan library to compare the current library with the saved baseline."
                )
            self._show_report("Changes since previous scan", text)
            return

        lines = [
            "PS5 FFPFSC RENAMER — CHANGES SINCE PREVIOUS SCAN",
            "",
            f"Previous scan: {self._format_snapshot_time(diff.previous_created_at)}",
            f"Current scan:  {self._format_snapshot_time(diff.current_created_at)}",
            f"Library roots changed: {'YES' if diff.roots_changed else 'no'}",
            "",
            f"Added: {len(diff.added)}",
            f"Removed: {len(diff.removed)}",
            f"Changed: {len(diff.changed)}",
        ]

        if not diff.has_changes:
            lines.extend(("", "No library changes were detected."))
        if diff.added:
            lines.extend(("", "ADDED"))
            lines.extend(self._entry_line("+", entry) for entry in diff.added[:100])
        if diff.removed:
            lines.extend(("", "REMOVED"))
            lines.extend(self._entry_line("-", entry) for entry in diff.removed[:100])
        if diff.changed:
            lines.extend(("", "CHANGED"))
            for change in diff.changed[:100]:
                lines.append(self._entry_line("~", change.after))
                lines.append(f"    Changed fields: {', '.join(change.fields)}")
                if change.before.status != change.after.status:
                    lines.append(
                        f"    Status: {change.before.status} -> {change.after.status}"
                    )
                if change.before.version != change.after.version:
                    lines.append(
                        f"    Version: {change.before.version} -> {change.after.version}"
                    )

        omitted = max(0, len(diff.added) - 100) + max(0, len(diff.removed) - 100) + max(0, len(diff.changed) - 100)
        if omitted:
            lines.extend(("", f"Report abbreviated: {omitted} additional change(s) not shown."))
        self._show_report("Changes since previous scan", "\n".join(lines))
