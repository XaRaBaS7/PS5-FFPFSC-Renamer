from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, replace
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from send2trash import send2trash

from .cache import quick_fingerprint
from .diagnostics import classify_reader_error, diagnose_image, infer_metadata_from_path
from .ffpfsc_reader import MetadataReadError, read_metadata
from .gui_v8 import RenamerApp as RenamerAppV8
from .library_view import (
    ResultRow,
    duplicate_title_ids,
    human_size,
    matches_filter,
    matches_search,
    safe_file_size,
)
from .rename_plan import PlanStatus, RenamePlanItem
from .renamer import apply_rename_plan
from .settings import AppSettings, load_settings, save_settings
from .theme import COLORS


@dataclass(slots=True)
class _Record:
    view: ResultRow
    plan_item: RenamePlanItem | None = None
    detail: str = ""
    friendly: str = ""
    inference_source: str = ""


class RenamerApp(RenamerAppV8):
    """Full library workspace: persistence, search, filters, size and multi-select actions."""

    FILTERS = (
        "ALL",
        "READY",
        "UNCHANGED",
        "PARTIAL",
        "COLLISION",
        "INVALID",
        "ERROR",
        "DUPLICATES",
    )

    def __init__(self) -> None:
        self._prefs_ready = False
        self._save_after_id: str | None = None
        self._all_records: list[_Record] = []
        self._row_records: dict[str, _Record] = {}
        self._duplicate_groups: dict[str, list[_Record]] = {}
        super().__init__()

        settings = load_settings()
        self._apply_settings(settings)
        self._prefs_ready = True
        self._install_setting_watchers()
        self._rebuild_output_plan(option_change=False)

    # ------------------------------------------------------------ settings
    def _apply_settings(self, settings: AppSettings) -> None:
        if settings.library_roots:
            self.library_roots = [Path(value) for value in settings.library_roots]
            self._update_root_summary()

        self.recursive_var.set(settings.recursive)
        if settings.worker in tuple(self.worker_combo.cget("values")):
            self.worker_var.set(settings.worker)

        preset_values = tuple(self.preset_combo.cget("values"))
        self.preset_var.set(settings.preset if settings.preset in preset_values else self.PRESET_CUSTOM)
        self.include_id_var.set(settings.include_title_id)
        self.include_title_var.set(settings.include_title)
        self.include_version_var.set(settings.include_version)
        self.version_format_var.set(settings.version_format)
        self.version_prefix_var.set(settings.version_prefix)

        folder_values = tuple(self.folder_mode_combo.cget("values"))
        if settings.folder_mode in folder_values:
            self.folder_mode_var.set(settings.folder_mode)

        self.component_order[:] = list(settings.component_order)
        self._render_order_editor()
        self._update_folder_help()
        self.filter_var.set(settings.result_filter if settings.result_filter in self.FILTERS else "ALL")

        if settings.window_geometry:
            try:
                self.geometry(settings.window_geometry)
            except tk.TclError:
                pass
        self._refresh_output_preview()

    def _snapshot_settings(self) -> AppSettings:
        geometry = None
        try:
            geometry = self.geometry()
        except tk.TclError:
            pass
        return AppSettings(
            library_roots=tuple(str(root) for root in self.library_roots),
            recursive=bool(self.recursive_var.get()),
            worker=self.worker_var.get(),
            preset=self.preset_var.get(),
            include_title_id=bool(self.include_id_var.get()),
            include_title=bool(self.include_title_var.get()),
            include_version=bool(self.include_version_var.get()),
            version_format=self.version_format_var.get(),
            version_prefix=bool(self.version_prefix_var.get()),
            folder_mode=self.folder_mode_var.get(),
            component_order=tuple(self.component_order),
            result_filter=self.filter_var.get(),
            window_geometry=geometry,
        )

    def _queue_save_preferences(self, *_args) -> None:
        if not self._prefs_ready:
            return
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except tk.TclError:
                pass
        self._save_after_id = self.after(250, self._save_preferences_now)

    def _save_preferences_now(self) -> None:
        self._save_after_id = None
        if not self._prefs_ready:
            return
        try:
            save_settings(self._snapshot_settings())
        except OSError:
            pass

    def _install_setting_watchers(self) -> None:
        for variable in (
            self.recursive_var,
            self.worker_var,
            self.preset_var,
            self.include_id_var,
            self.include_title_var,
            self.include_version_var,
            self.version_format_var,
            self.version_prefix_var,
            self.folder_mode_var,
            self.filter_var,
        ):
            variable.trace_add("write", self._queue_save_preferences)
        self.bind("<Configure>", self._queue_save_preferences, add="+")
        self.protocol("WM_DELETE_WINDOW", self._close_with_settings)

    def _close_with_settings(self) -> None:
        self._save_preferences_now()
        self.destroy()

    def _update_root_summary(self) -> None:
        super()._update_root_summary()
        self._queue_save_preferences()

    def _move_component(self, index: int, direction: int) -> None:
        super()._move_component(index, direction)
        self._queue_save_preferences()

    def _apply_preset(self, event=None) -> None:
        super()._apply_preset(event)
        self._queue_save_preferences()

    # -------------------------------------------------------------- table
    def _build_table(self, parent) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(8, 0))

        ttk.Label(toolbar, text="Search", style="CardMuted.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        search = tk.Entry(
            toolbar,
            textvariable=self.search_var,
            bg="#211a2f",
            fg="#f4f0ff",
            insertbackground="#f4f0ff",
            selectbackground="#8b5cf6",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#3a304d",
            highlightcolor="#8b5cf6",
            relief="flat",
            font=("Segoe UI", 9),
            width=34,
        )
        search.pack(side="left", padx=(6, 12), ipady=5)

        ttk.Label(toolbar, text="Filter", style="CardMuted.TLabel").pack(side="left")
        self.filter_var = tk.StringVar(value="ALL")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=self.FILTERS,
            state="readonly",
            width=13,
            style="Performance.TCombobox",
        )
        filter_combo.pack(side="left", padx=(6, 0))

        self.result_count_var = tk.StringVar(value="0 results")
        ttk.Label(toolbar, textvariable=self.result_count_var, style="CardMuted.TLabel").pack(
            side="right"
        )

        super()._build_table(parent)
        columns = ("file", "title_id", "title", "version", "size", "output", "status")
        self.tree.configure(columns=columns, selectmode="extended")
        headings = {
            "file": "Current file",
            "title_id": "Title ID",
            "title": "Title",
            "version": "Version",
            "size": "Size",
            "output": "Proposed output",
            "status": "Status",
        }
        widths = {
            "file": 300,
            "title_id": 105,
            "title": 230,
            "version": 100,
            "size": 85,
            "output": 330,
            "status": 95,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=70, anchor="w")
        self.tree.tag_configure("partial", foreground=COLORS["warning"])

        self.search_var.trace_add("write", lambda *_: self._render_records())
        self.filter_var.trace_add("write", lambda *_: self._render_records())
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", self._double_click, add="+")

    def _record_model(self) -> list[_Record]:
        records: list[_Record] = []
        for item in self.plan:
            metadata = item.metadata
            records.append(
                _Record(
                    ResultRow(
                        source=item.source,
                        title_id=metadata.title_id,
                        title=metadata.title_name or "-",
                        version=metadata.content_version or metadata.master_version or "-",
                        size=safe_file_size(item.source),
                        output=self._display_destination(item),
                        status=item.status.value.upper(),
                    ),
                    plan_item=item,
                )
            )

        for image, metadata, detail, inference_source, _code, friendly in self.partial_items:
            records.append(
                _Record(
                    ResultRow(
                        source=image,
                        title_id=metadata.title_id,
                        title=metadata.title_name or "-",
                        version="-",
                        size=safe_file_size(image),
                        output="-",
                        status="PARTIAL",
                    ),
                    detail=detail,
                    friendly=friendly,
                    inference_source=inference_source,
                )
            )

        for image, detail in self.scan_errors:
            _code, friendly = classify_reader_error(detail)
            records.append(
                _Record(
                    ResultRow(
                        source=image,
                        title_id="-",
                        title="Metadata unavailable",
                        version="-",
                        size=safe_file_size(image),
                        output="-",
                        status="ERROR",
                    ),
                    detail=detail,
                    friendly=friendly,
                )
            )

        duplicate_ids = duplicate_title_ids([record.view for record in records])
        result: list[_Record] = []
        for record in records:
            is_duplicate = record.view.title_id.upper() in duplicate_ids
            record.view = replace(record.view, duplicate=is_duplicate)
            result.append(record)
        return result

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        # Parent layers continue to own the rename plan and safety counters.
        # Their temporary six-column rows are replaced immediately below by
        # this richer seven-column view.
        super()._rebuild_output_plan(option_change=option_change)
        self._all_records = self._record_model()
        self._duplicate_groups = {}
        for record in self._all_records:
            if record.view.duplicate and record.view.title_id != "-":
                self._duplicate_groups.setdefault(record.view.title_id.upper(), []).append(record)
        self._render_records()

    def _render_records(self) -> None:
        if not hasattr(self, "tree"):
            return
        query = self.search_var.get() if hasattr(self, "search_var") else ""
        selected_filter = self.filter_var.get() if hasattr(self, "filter_var") else "ALL"
        visible = [
            record
            for record in self._all_records
            if matches_search(record.view, query) and matches_filter(record.view, selected_filter)
        ]

        self._hide_tree_tooltip()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._row_plan_items.clear()
        self._row_sources.clear()
        self._row_tooltips.clear()
        self._row_records.clear()

        for record in visible:
            view = record.view
            tags = (view.status.lower(),)
            row = self.tree.insert(
                "",
                "end",
                values=(
                    self._display_source(view.source),
                    view.title_id,
                    view.title,
                    view.version,
                    human_size(view.size),
                    view.output,
                    view.status,
                ),
                tags=tags,
            )
            self._row_records[row] = record
            self._row_sources[row] = view.source
            if record.plan_item is not None:
                self._row_plan_items[row] = record.plan_item
                if record.plan_item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}:
                    self._row_tooltips[row] = (
                        f"{view.status}\n{self._friendly_reason(record.plan_item.reason)}\n"
                        f"Source: {self._display_source(view.source)}\n"
                        f"Target: {record.plan_item.destination}"
                    )
            elif view.status == "PARTIAL":
                self._row_tooltips[row] = (
                    f"PARTIAL\n{record.friendly}\n"
                    f"Detected from: {record.inference_source}\n"
                    "The displayed metadata was not verified inside the FFPFSC. "
                    "Automatic rename remains disabled for this row."
                )
            elif view.status == "ERROR":
                self._row_tooltips[row] = (
                    f"ERROR\n{record.friendly}\n"
                    "Right-click and choose Run diagnostics for technical details."
                )

        self.result_count_var.set(f"{len(visible)} of {len(self._all_records)} results")

    # ----------------------------------------------------------- tooltips
    def _show_tooltip_text(self, row: str, text: str) -> None:
        if self._tooltip_window is not None and self._tooltip_row == row:
            return
        self._hide_tree_tooltip()
        self._tooltip_row = row
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(
            tooltip,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["accent"],
        )
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame,
            text=text,
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
            wraplength=470,
        ).pack()
        tooltip.wm_geometry(f"+{self.tree.winfo_pointerx() + 14}+{self.tree.winfo_pointery() + 16}")
        self._tooltip_window = tooltip

    def _on_tree_motion(self, event) -> None:
        row = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not row:
            self._hide_tree_tooltip()
            return
        record = self._row_records.get(row)
        if record is None:
            self._hide_tree_tooltip()
            return

        if column == "#7" and row in self._row_tooltips:
            self._show_tooltip_text(row, self._row_tooltips[row])
            return
        if column == "#2" and record.view.duplicate:
            group = self._duplicate_groups.get(record.view.title_id.upper(), [])
            self._show_tooltip_text(
                row,
                f"DUPLICATE TITLE ID\n{record.view.title_id} appears in {len(group)} files.\n"
                "Right-click and choose Compare duplicates to inspect paths, sizes and quick fingerprints.",
            )
            return
        self._hide_tree_tooltip()

    # ------------------------------------------------------- context menu
    def _selected_records(self) -> list[_Record]:
        return [
            self._row_records[row]
            for row in self.tree.selection()
            if row in self._row_records
        ]

    def _show_context_menu(self, event) -> str:
        row = self.tree.identify_row(event.y)
        if not row:
            return "break"
        self._hide_tree_tooltip()
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        records = self._selected_records()
        if not records:
            return "break"

        menu = tk.Menu(
            self,
            tearoff=False,
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            activebackground=COLORS["accent"],
            activeforeground="#ffffff",
            bd=1,
            relief="solid",
        )

        if len(records) > 1:
            ready = [r.plan_item for r in records if r.plan_item and r.plan_item.status is PlanStatus.READY]
            menu.add_command(
                label=f"Rename selected using current plan ({len(ready)} ready)",
                command=lambda items=ready: self._rename_selected_items(items),
                state="normal" if ready else "disabled",
            )
            menu.add_command(
                label=f"Analyze selected again ({len(records)})",
                command=lambda paths=[r.view.source for r in records]: self._analyze_paths(paths),
            )
            menu.add_separator()
            menu.add_command(
                label="Copy selected paths",
                command=lambda values=[str(r.view.source) for r in records]: self._copy_text("\n".join(values)),
            )
            menu.add_command(
                label=f"Delete selected to Recycle Bin... ({len(records)})",
                command=lambda chosen=records: self._delete_records(chosen),
            )
        else:
            record = records[0]
            item = record.plan_item
            if item is not None:
                menu.add_command(
                    label="Rename using current plan",
                    command=lambda selected=item: self._rename_selected_plan(selected),
                    state="normal" if item.status is PlanStatus.READY else "disabled",
                )
            menu.add_command(
                label="Rename file manually...",
                command=lambda path=record.view.source: self._manual_rename(path),
            )
            menu.add_separator()
            menu.add_command(
                label="Show in Explorer",
                command=lambda path=record.view.source: self._show_in_explorer(path),
            )
            menu.add_command(
                label="Open folder",
                command=lambda path=record.view.source: self._open_folder(path),
            )
            menu.add_command(
                label="Run diagnostics",
                command=lambda path=record.view.source: self._run_diagnostics(path),
            )
            menu.add_separator()
            menu.add_command(
                label="Copy full path",
                command=lambda path=record.view.source: self._copy_text(str(path)),
            )
            if record.view.title_id != "-":
                menu.add_command(
                    label="Copy Title ID / PPSA",
                    command=lambda value=record.view.title_id: self._copy_text(value),
                )
            menu.add_command(
                label="Show details",
                command=lambda selected=record: self._show_record_details(selected),
            )
            menu.add_command(
                label="Analyze again",
                command=lambda path=record.view.source: self._analyze_paths([path]),
            )
            if record.view.duplicate:
                menu.add_command(
                    label=f"Compare duplicates ({len(self._duplicate_groups.get(record.view.title_id.upper(), []))})",
                    command=lambda title_id=record.view.title_id: self._compare_duplicates(title_id),
                )
            if item is not None and item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}:
                menu.add_command(
                    label="Why blocked?",
                    command=lambda selected=item: self._show_block_reason(selected),
                )
            menu.add_separator()
            menu.add_command(
                label="Delete (move to Recycle Bin)...",
                command=lambda chosen=[record]: self._delete_records(chosen),
            )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _double_click(self, event) -> str:
        row = self.tree.identify_row(event.y)
        record = self._row_records.get(row)
        if record is None:
            return "break"
        if record.view.status in {"PARTIAL", "ERROR"}:
            self._run_diagnostics(record.view.source)
        else:
            self._show_record_details(record)
        return "break"

    # ----------------------------------------------------------- actions
    def _show_record_details(self, record: _Record) -> None:
        text = (
            f"File: {record.view.source.name}\n"
            f"Path: {record.view.source}\n"
            f"Size: {human_size(record.view.size)}\n\n"
            f"Title ID: {record.view.title_id}\n"
            f"Title: {record.view.title}\n"
            f"Version: {record.view.version}\n"
            f"Proposed output: {record.view.output}\n"
            f"Status: {record.view.status}"
        )
        if record.view.duplicate:
            text += "\nDuplicate Title ID: yes"
        if record.friendly:
            text += f"\n\nNote: {record.friendly}"
        messagebox.showinfo("FFPFSC details", text, parent=self)

    def _run_diagnostics(self, path: Path) -> None:
        if self._scan_active:
            messagebox.showinfo("Diagnostics", "Wait for the current library scan to finish first.", parent=self)
            return
        self.status_var.set(f"Running diagnostics: {path.name}...")

        def worker() -> None:
            try:
                report = diagnose_image(path, library_root=self._matching_root(path), timeout=45)
            except Exception as exc:
                report = f"Diagnostics failed:\n{exc}"
            self.after(0, lambda: self._show_report("FFPFSC diagnostics", report))

        threading.Thread(target=worker, daemon=True).start()

    def _show_report(self, title: str, text: str) -> None:
        self.status_var.set("Ready")
        window = tk.Toplevel(self)
        window.title(title)
        window.transient(self)
        window.geometry("900x620")
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        box = tk.Text(
            frame,
            wrap="word",
            bg="#181321",
            fg="#f4f0ff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Consolas", 9),
        )
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.configure(state="disabled")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Copy report", command=lambda: self._copy_text(text)).pack(side="left")
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

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
            "No FFPFSC contents will be rewritten or recompressed.",
            parent=self,
        ):
            return
        try:
            completed = apply_rename_plan(unique)
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc), parent=self)
            return
        mapping = {old: new for old, new in completed}
        for old, new in completed:
            try:
                self.cache.update_path_after_rename(old, new)
            except Exception:
                pass
        self.parsed_items = [(mapping.get(path, path), metadata) for path, metadata in self.parsed_items]
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Renamed {len(completed)} selected file(s)")

    def _analyze_paths(self, paths: list[Path]) -> None:
        if self._scan_active:
            messagebox.showinfo("Analyze again", "Wait for the current library scan to finish first.", parent=self)
            return
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(path.resolve())
        if not unique:
            return
        self.status_var.set(f"Re-analyzing {len(unique)} file(s) with MkPFS...")

        def worker() -> None:
            successes: dict[Path, object] = {}
            failures: dict[Path, str] = {}
            for path in unique:
                try:
                    metadata = read_metadata(path, cache=self.cache, use_cache=False)
                    self.cache.store(path, metadata)
                    successes[path] = metadata
                except (MetadataReadError, OSError) as exc:
                    try:
                        self.cache.remove(path)
                    except Exception:
                        pass
                    failures[path] = str(exc)

            def done() -> None:
                selected_keys = {str(path).casefold() for path in unique}
                self.parsed_items = [
                    (path, metadata)
                    for path, metadata in self.parsed_items
                    if str(path.resolve()).casefold() not in selected_keys
                ]
                self.scan_errors = [
                    (path, detail)
                    for path, detail in self.scan_errors
                    if str(path.resolve()).casefold() not in selected_keys
                ]
                self.partial_items = [
                    item
                    for item in self.partial_items
                    if str(item[0].resolve()).casefold() not in selected_keys
                ]

                for path, metadata in successes.items():
                    self.parsed_items.append((path, metadata))
                for path, detail in failures.items():
                    inferred = infer_metadata_from_path(path, library_root=self._matching_root(path))
                    code, friendly = classify_reader_error(detail)
                    if inferred is not None:
                        self.partial_items.append(
                            (path, inferred.metadata, detail, inferred.source, code, friendly)
                        )
                    else:
                        self.scan_errors.append((path, detail))

                self.cache_entries_var.set(str(self.cache.entry_count()))
                self._rebuild_output_plan(option_change=True)
                self.status_var.set(
                    f"Re-analysis complete — {len(successes)} verified, {len(failures)} partial/error"
                )

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _delete_records(self, records: list[_Record]) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for record in records:
            path = record.view.source.resolve()
            key = str(path).casefold()
            if key not in seen and path.exists():
                seen.add(key)
                unique.append(path)
        if not unique:
            return
        total_size = sum((safe_file_size(path) or 0) for path in unique)
        if not messagebox.askyesno(
            "Move to Recycle Bin",
            f"Move {len(unique)} selected file(s) ({human_size(total_size)}) to the Windows Recycle Bin?\n\n"
            "This action does not permanently delete them.",
            icon="warning",
            parent=self,
        ):
            return

        removed: list[Path] = []
        errors: list[str] = []
        for path in unique:
            try:
                send2trash(str(path))
                removed.append(path)
                try:
                    self.cache.remove(path)
                except Exception:
                    pass
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        removed_keys = {str(path).casefold() for path in removed}
        self.parsed_items = [
            (path, metadata)
            for path, metadata in self.parsed_items
            if str(path.resolve()).casefold() not in removed_keys
        ]
        self.scan_errors = [
            (path, detail)
            for path, detail in self.scan_errors
            if str(path.resolve()).casefold() not in removed_keys
        ]
        self.partial_items = [
            item for item in self.partial_items if str(item[0].resolve()).casefold() not in removed_keys
        ]
        self.files_var.set(str(max(0, int(self.files_var.get() or "0") - len(removed))))
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(f"Moved {len(removed)} file(s) to Recycle Bin")
        if errors:
            messagebox.showwarning("Recycle Bin", "Some files could not be moved:\n\n" + "\n".join(errors[:8]), parent=self)

    def _compare_duplicates(self, title_id: str) -> None:
        group = list(self._duplicate_groups.get(title_id.upper(), []))
        if len(group) < 2:
            return
        self.status_var.set(f"Comparing duplicates: {title_id}...")

        def worker() -> None:
            lines = [f"DUPLICATE COMPARISON — {title_id}", ""]
            fingerprints: list[tuple[int | None, str | None]] = []
            for index, record in enumerate(group, start=1):
                path = record.view.source
                fingerprint = None
                try:
                    fingerprint = quick_fingerprint(path)
                except OSError:
                    pass
                fingerprints.append((record.view.size, fingerprint))
                lines.extend(
                    (
                        f"[{index}] {record.view.title}",
                        f"Path: {path}",
                        f"Version: {record.view.version}",
                        f"Size: {human_size(record.view.size)}",
                        f"Status: {record.view.status}",
                        f"Quick fingerprint: {fingerprint or 'unavailable'}",
                        "",
                    )
                )
            comparable = [value for value in fingerprints if value[1] is not None]
            same = bool(comparable) and len(set(comparable)) == 1 and len(comparable) == len(group)
            lines.append(
                "Assessment: sampled size/fingerprint matches for every file."
                if same
                else "Assessment: files differ in size and/or sampled fingerprint, or a sample could not be read."
            )
            lines.append(
                "Note: the quick fingerprint reads only small samples and is an identity hint, not a full-file checksum."
            )
            report = "\n".join(lines)
            self.after(0, lambda: self._show_report(f"Duplicates — {title_id}", report))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
