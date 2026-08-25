from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .diagnostics import classify_reader_error, infer_metadata_from_path
from .ffpfsc_reader import (
    MetadataReadCancelled,
    MetadataReadError,
    _mkpfs_command,
    mkpfs_source_description,
    read_metadata,
    set_mkpfs_executable,
)
from .gui_v9 import RenamerApp as RenamerAppV9, _Record
from .library_export import ExportRow, export_csv, export_json
from .library_view import human_size
from .metadata import GameMetadata
from .operation_history import HistoryError, HistoryTransaction, OperationHistory
from .rename_plan import PlanStatus, RenamePlanItem
from .renamer import RenameStep, apply_rename_plan, build_forward_steps
from .scanner import scan_ffpfsc
from .settings import AppSettings, load_settings
from .theme import COLORS


class RenamerApp(RenamerAppV9):
    """v0.3 reliability/performance workspace.

    Adds durable undo history, atomic batch behavior, export/health tools,
    custom MkPFS selection, sortable results and a negative cache so unchanged
    problematic images do not repeatedly pay the MkPFS parsing cost.
    """

    SORTABLE_COLUMNS = {
        "file": "Current file",
        "title_id": "Title ID",
        "title": "Title",
        "version": "Version",
        "size": "Size",
        "output": "Proposed output",
        "status": "Status",
    }
    STATUS_ORDER = {
        "READY": 0,
        "UNCHANGED": 1,
        "PARTIAL": 2,
        "COLLISION": 3,
        "INVALID": 4,
        "ERROR": 5,
    }

    def __init__(self) -> None:
        initial_settings = load_settings()
        self._mkpfs_path: str | None = initial_settings.mkpfs_path
        self._sort_column = (
            initial_settings.sort_column
            if initial_settings.sort_column in self.SORTABLE_COLUMNS
            else "file"
        )
        self._sort_descending = bool(initial_settings.sort_descending)
        self._last_unavailable_roots: tuple[str, ...] = ()
        set_mkpfs_executable(self._mkpfs_path)
        self.history = OperationHistory()
        self._last_failure_cache_hits = 0
        super().__init__()
        self._build_product_menu()
        self._install_shortcuts()
        self._refresh_sort_headings()

    # ------------------------------------------------------------ settings
    def _snapshot_settings(self) -> AppSettings:
        return replace(
            super()._snapshot_settings(),
            mkpfs_path=self._mkpfs_path,
            sort_column=self._sort_column,
            sort_descending=self._sort_descending,
        )

    # --------------------------------------------------------------- table
    def _build_table(self, parent) -> None:
        super()._build_table(parent)
        for column, label in self.SORTABLE_COLUMNS.items():
            self.tree.heading(
                column,
                text=label,
                command=lambda selected=column: self._sort_by_column(selected),
            )
        self._refresh_sort_headings()

    def _render_records(self) -> None:
        super()._render_records()
        self._apply_tree_sort()
        if hasattr(self, "result_count_var"):
            visible = [
                self._row_records[row]
                for row in self.tree.get_children()
                if row in self._row_records
            ]
            visible_size = sum(record.view.size or 0 for record in visible)
            self.result_count_var.set(
                f"{len(visible)} of {len(self._all_records)} results • {human_size(visible_size)}"
            )

    @staticmethod
    def _version_key(value: str) -> tuple[tuple[int, ...], str]:
        numbers = tuple(int(part) for part in re.findall(r"\d+", value))
        return numbers, value.casefold()

    def _sort_key(self, record: _Record, column: str):
        view = record.view
        if column == "size":
            return view.size if view.size is not None else -1
        if column == "version":
            return self._version_key(view.version)
        if column == "status":
            return self.STATUS_ORDER.get(view.status, 99), view.status.casefold()
        if column == "title_id":
            return view.title_id.casefold()
        if column == "title":
            return view.title.casefold()
        if column == "output":
            return view.output.casefold()
        return self._display_source(view.source).casefold()

    def _apply_tree_sort(self) -> None:
        if not hasattr(self, "tree") or not hasattr(self, "_row_records"):
            return
        rows = [row for row in self.tree.get_children() if row in self._row_records]
        rows.sort(
            key=lambda row: self._sort_key(self._row_records[row], self._sort_column),
            reverse=self._sort_descending,
        )
        for index, row in enumerate(rows):
            self.tree.move(row, "", index)
        self._refresh_sort_headings()

    def _sort_by_column(self, column: str) -> None:
        if column not in self.SORTABLE_COLUMNS:
            return
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._apply_tree_sort()
        self._queue_save_preferences()

    def _refresh_sort_headings(self) -> None:
        if not hasattr(self, "tree"):
            return
        for column, label in self.SORTABLE_COLUMNS.items():
            arrow = ""
            if column == self._sort_column:
                arrow = " ▼" if self._sort_descending else " ▲"
            try:
                self.tree.heading(column, text=label + arrow)
            except tk.TclError:
                pass

    # --------------------------------------------------------------- menu
    def _build_product_menu(self) -> None:
        menubar = tk.Menu(self, tearoff=False)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Scan library\tF5", command=self._scan)
        file_menu.add_separator()

        export_menu = tk.Menu(file_menu, tearoff=False)
        export_menu.add_command(
            label="Full library as CSV...",
            command=lambda: self._export_library("csv", visible_only=False),
        )
        export_menu.add_command(
            label="Full library as JSON...",
            command=lambda: self._export_library("json", visible_only=False),
        )
        export_menu.add_separator()
        export_menu.add_command(
            label="Visible results as CSV...",
            command=lambda: self._export_library("csv", visible_only=True),
        )
        export_menu.add_command(
            label="Visible results as JSON...",
            command=lambda: self._export_library("json", visible_only=True),
        )
        file_menu.add_cascade(label="Export", menu=export_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._close_with_settings)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Undo last rename\tCtrl+Z", command=self._undo_last_rename)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select all results\tCtrl+A", command=self._select_all_rows)
        edit_menu.add_command(
            label="Clear selection",
            command=lambda: self.tree.selection_remove(self.tree.selection()),
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

        tools_menu = tk.Menu(menubar, tearoff=False)
        tools_menu.add_command(label="Operation history...", command=self._show_history_window)
        tools_menu.add_command(label="Library health report", command=self._show_library_health)
        tools_menu.add_command(
            label="Re-analyze PARTIAL / ERROR...",
            command=self._reanalyze_problem_rows,
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Cache Manager...", command=self._show_cache_manager)
        tools_menu.add_command(label="MkPFS engine...", command=self._show_mkpfs_settings)
        tools_menu.add_command(label="Open app data folder", command=self._open_app_data_folder)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)
        self._product_menu = menubar

    def _install_shortcuts(self) -> None:
        self.bind("<F5>", lambda _event: self._shortcut_scan(), add="+")
        self.bind("<Control-z>", lambda _event: self._shortcut_undo(), add="+")
        self.bind("<Control-Z>", lambda _event: self._shortcut_undo(), add="+")
        self.bind("<Control-e>", lambda _event: self._shortcut_export(), add="+")
        self.bind("<Control-E>", lambda _event: self._shortcut_export(), add="+")
        self.bind("<Control-a>", lambda _event: self._shortcut_select_all(), add="+")
        self.bind("<Control-A>", lambda _event: self._shortcut_select_all(), add="+")

    def _shortcut_scan(self) -> str:
        if not self._scan_active:
            self._scan()
        return "break"

    def _shortcut_undo(self) -> str:
        if not self._scan_active:
            self._undo_last_rename()
        return "break"

    def _shortcut_export(self) -> str:
        self._export_library("csv", visible_only=False)
        return "break"

    def _shortcut_select_all(self) -> str:
        self._select_all_rows()
        return "break"

    # ------------------------------------------------------ optimized scan
    def _scan_worker(self, folder: Path, recursive: bool, worker_setting: str) -> None:
        started_at = time.monotonic()
        roots = list(self.library_roots) or [folder]
        images: list[Path] = []
        seen: set[str] = set()
        unavailable: list[str] = []
        accessible_roots = 0

        for root in roots:
            try:
                if not root.exists() or not root.is_dir():
                    unavailable.append(f"{root} — unavailable")
                    continue
                discovered = scan_ffpfsc(root, recursive=recursive)
                accessible_roots += 1
            except Exception as exc:
                unavailable.append(f"{root} — {exc}")
                continue
            for image in discovered:
                resolved = image.resolve()
                key = str(resolved).casefold()
                if key in seen:
                    continue
                seen.add(key)
                images.append(resolved)

        self._last_unavailable_roots = tuple(unavailable)
        if accessible_roots == 0 and roots:
            detail = "No selected library root is currently accessible."
            if unavailable:
                detail += "\n\n" + "\n".join(unavailable[:10])
            self.after(0, lambda text=detail: self._scan_failed(text))
            return

        images.sort(key=lambda path: str(path).casefold())
        total = len(images)
        self.after(0, lambda: self.files_var.set(str(total)))

        # One SQLite read replaces one connection/PRAGMA cycle per FFPFSC.
        try:
            verified_lookups = self.cache.lookup_many(images)
        except Exception:
            verified_lookups = {}
        try:
            failure_lookups = self.cache.lookup_failures_many(images)
        except Exception:
            failure_lookups = {}

        cached_items: list[tuple[Path, GameMetadata]] = []
        cached_errors: list[tuple[Path, str]] = []
        misses: list[Path] = []

        for index, image in enumerate(images, start=1):
            if self.cancel_event.is_set():
                self.after(0, lambda: self._scan_cancelled(index - 1, total))
                return

            verified = verified_lookups.get(image)
            if verified is not None and verified.hit and verified.metadata is not None:
                cached_items.append((image, verified.metadata))
            else:
                failed = failure_lookups.get(image)
                if failed is not None and failed.hit and failed.error:
                    cached_errors.append((image, failed.error))
                else:
                    misses.append(image)

            cached_count = len(cached_items) + len(cached_errors)
            self.after(
                0,
                lambda done=index, hits=cached_count, new=len(misses): self._cache_check_progress(
                    done, total, hits, new
                ),
            )

        cache_hits = len(cached_items) + len(cached_errors)
        failure_cache_hits = len(cached_errors)
        self._last_failure_cache_hits = failure_cache_hits
        workers = self._resolve_worker_count(worker_setting, len(misses))
        self.after(0, lambda: self._analysis_started(total, cache_hits, len(misses), workers))

        parsed = list(cached_items)
        errors = list(cached_errors)
        completed = cache_hits
        mkpfs_reads = 0

        if not misses:
            self.after(
                0,
                lambda: self._scan_complete(
                    parsed, errors, total, started_at, workers, cache_hits, 0
                ),
            )
            return

        def read_one(image: Path) -> GameMetadata:
            return read_metadata(
                image,
                timeout=120,
                cancel_event=self.cancel_event,
                use_cache=False,
            )

        def remember_failure(image: Path, detail: str) -> None:
            try:
                self.cache.store_failure(image, detail)
            except Exception:
                pass

        if workers == 1:
            for image in misses:
                if self.cancel_event.is_set():
                    break
                try:
                    metadata = read_one(image)
                    parsed.append((image, metadata))
                    try:
                        self.cache.store(image, metadata)
                    except Exception:
                        pass
                except MetadataReadCancelled:
                    break
                except MetadataReadError as exc:
                    detail = str(exc)
                    errors.append((image, detail))
                    remember_failure(image, detail)
                except Exception as exc:
                    detail = f"Unexpected error: {exc}"
                    errors.append((image, detail))
                    remember_failure(image, detail)

                completed += 1
                mkpfs_reads += 1
                self.after(
                    0,
                    lambda done=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                        done, total, started_at, name, workers, cache_hits, reads
                    ),
                )
        else:
            executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ffpfsc-reader")
            future_to_image = {executor.submit(read_one, image): image for image in misses}
            pending = set(future_to_image)
            try:
                while pending and not self.cancel_event.is_set():
                    done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                    for future in done:
                        image = future_to_image[future]
                        try:
                            metadata = future.result()
                            parsed.append((image, metadata))
                            try:
                                self.cache.store(image, metadata)
                            except Exception:
                                pass
                        except MetadataReadCancelled:
                            self.cancel_event.set()
                            break
                        except MetadataReadError as exc:
                            detail = str(exc)
                            errors.append((image, detail))
                            remember_failure(image, detail)
                        except Exception as exc:
                            detail = f"Unexpected error: {exc}"
                            errors.append((image, detail))
                            remember_failure(image, detail)

                        completed += 1
                        mkpfs_reads += 1
                        self.after(
                            0,
                            lambda done_count=completed, name=image.name, reads=mkpfs_reads: self._progress_update(
                                done_count, total, started_at, name, workers, cache_hits, reads
                            ),
                        )
            finally:
                if self.cancel_event.is_set():
                    for future in pending:
                        future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(completed, total))
            return

        self.after(
            0,
            lambda: self._scan_complete(
                parsed, errors, total, started_at, workers, cache_hits, mkpfs_reads
            ),
        )

    def _scan_complete(
        self,
        parsed: list[tuple[Path, GameMetadata]],
        errors: list[tuple[Path, str]],
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
        additions: list[str] = []
        if self._last_failure_cache_hits:
            additions.append(
                f"{self._last_failure_cache_hits} unchanged previous error(s) were reused without launching MkPFS."
            )
        if self._last_unavailable_roots:
            additions.append(
                f"{len(self._last_unavailable_roots)} unavailable library root(s) were skipped."
            )
        if additions:
            self.progress_note_var.set(self.progress_note_var.get() + " " + " ".join(additions))

    # ------------------------------------------------------- rename journal
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
        try:
            self.history.record(label=label, pairs=completed, steps=steps)
        except Exception as exc:
            messagebox.showwarning(
                "Operation history",
                "The rename completed, but its Undo journal could not be saved.\n\n"
                f"{exc}",
                parent=self,
            )

        self._update_in_memory_paths(dict(completed))
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(
            f"{label}: {len(completed)} file(s) completed — Ctrl+Z can undo the latest transaction"
        )

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
            "The completed transaction is also added to Operation History and can be undone with Ctrl+Z."
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
            messagebox.showinfo(
                "PS5 FFPFSC Renamer",
                f"Completed {len(completed)} file operation(s).\n\n"
                "No rescan is required: paths and cache were updated in memory.\n"
                "Press Ctrl+Z if you want to undo this transaction.",
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
            "The transaction is rollback-protected and can be undone with Ctrl+Z.",
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
            "This action can be undone with Ctrl+Z.",
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

    # --------------------------------------------------------------- undo
    def _undo_last_rename(self) -> None:
        transaction = self.history.last_undoable()
        if transaction is None:
            messagebox.showinfo("Undo rename", "There is no rename transaction to undo.", parent=self)
            return
        self._undo_transaction(transaction)

    def _undo_transaction(self, transaction: HistoryTransaction) -> None:
        created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
        if not messagebox.askyesno(
            "Undo rename transaction",
            f"Restore the previous paths for this transaction?\n\n"
            f"{transaction.label}\n{created}\n{transaction.item_count} file(s)\n\n"
            "Undo never overwrites an existing original path.",
            parent=self,
        ):
            return
        try:
            result = self.history.undo(transaction.transaction_id)
        except HistoryError as exc:
            messagebox.showerror("Undo blocked", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Undo failed", str(exc), parent=self)
            return

        mapping = dict(result.restored_pairs)
        for current_path, restored_path in result.restored_pairs:
            try:
                self.cache.update_path_after_rename(current_path, restored_path)
            except Exception:
                pass
        self._update_in_memory_paths(mapping)
        self.cache_entries_var.set(str(self.cache.entry_count()))
        self._rebuild_output_plan(option_change=True)
        self.status_var.set(
            f"Undone: {result.transaction.label} — restored {len(result.restored_pairs)} file(s)"
        )
        if result.retained_directories:
            messagebox.showwarning(
                "Undo completed with retained folders",
                "The files were restored, but these application-created folders were not empty and were left untouched:\n\n"
                + "\n".join(str(path) for path in result.retained_directories),
                parent=self,
            )

    # ------------------------------------------------------ force analysis
    def _analyze_paths(self, paths: list[Path]) -> None:
        if self._scan_active:
            messagebox.showinfo("Analyze again", "Wait for the current library scan to finish first.", parent=self)
            return
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            key = str(resolved).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(resolved)
        if not unique:
            return
        self.status_var.set(f"Re-analyzing {len(unique)} file(s) with MkPFS...")

        def worker() -> None:
            successes: dict[Path, GameMetadata] = {}
            failures: dict[Path, str] = {}
            for path in unique:
                try:
                    metadata = read_metadata(path, cache=self.cache, use_cache=False)
                    self.cache.store(path, metadata)
                    successes[path] = metadata
                except (MetadataReadError, OSError) as exc:
                    detail = str(exc)
                    try:
                        self.cache.store_failure(path, detail)
                    except Exception:
                        pass
                    failures[path] = detail

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

    def _reanalyze_problem_rows(self) -> None:
        problem_paths = [
            record.view.source
            for record in self._all_records
            if record.view.status in {"PARTIAL", "ERROR"}
        ]
        if not problem_paths:
            messagebox.showinfo("Re-analyze", "There are no PARTIAL or ERROR rows in the current library.", parent=self)
            return
        if not messagebox.askyesno(
            "Re-analyze problematic files",
            f"Force MkPFS to analyze {len(problem_paths)} PARTIAL/ERROR file(s) again?\n\n"
            "This bypasses the cached previous error for these files.",
            parent=self,
        ):
            return
        self._analyze_paths(problem_paths)

    # ------------------------------------------------------------- export
    @staticmethod
    def _export_row(record: _Record) -> ExportRow:
        view = record.view
        return ExportRow(
            path=str(view.source),
            filename=view.source.name,
            title_id=view.title_id,
            title=view.title,
            version=view.version,
            size_bytes=view.size,
            proposed_output=view.output,
            status=view.status,
            duplicate_title_id=view.duplicate,
        )

    def _export_library(self, format_name: str, *, visible_only: bool) -> None:
        if visible_only:
            records = [
                self._row_records[row]
                for row in self.tree.get_children()
                if row in self._row_records
            ]
        else:
            records = list(self._all_records)
        if not records:
            messagebox.showinfo("Export library", "There are no scan results to export.", parent=self)
            return

        format_name = format_name.lower()
        if format_name not in {"csv", "json"}:
            raise ValueError(format_name)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = "visible" if visible_only else "library"
        selected = filedialog.asksaveasfilename(
            title="Export FFPFSC library",
            parent=self,
            defaultextension=f".{format_name}",
            initialfile=f"PS5-FFPFSC-Renamer-{suffix}-{stamp}.{format_name}",
            filetypes=[
                ("CSV files", "*.csv") if format_name == "csv" else ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        destination = Path(selected)
        rows = [self._export_row(record) for record in records]
        try:
            if format_name == "csv":
                export_csv(rows, destination)
            else:
                export_json(rows, destination)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.status_var.set(f"Exported {len(rows)} result(s) to {destination.name}")
        if messagebox.askyesno(
            "Export complete",
            f"Exported {len(rows)} result(s).\n\nShow the file in Explorer?",
            parent=self,
        ):
            self._show_in_explorer(destination)

    # ------------------------------------------------------------- history
    @staticmethod
    def _transaction_summary(transaction: HistoryTransaction) -> str:
        created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"Transaction: {transaction.transaction_id}",
            f"Date: {created}",
            f"Action: {transaction.label}",
            f"Files: {transaction.item_count}",
            f"Status: {'UNDONE' if transaction.is_undone else 'APPLIED'}",
            "",
        ]
        for old, new in transaction.pairs:
            lines.extend((f"From: {old}", f"To:   {new}", ""))
        return "\n".join(lines).rstrip()

    def _show_history_window(self) -> None:
        window = tk.Toplevel(self)
        window.title("Operation history")
        window.transient(self)
        window.geometry("980x520")
        window.minsize(760, 380)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Rename transaction history", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Only the latest applied transaction can be undone. History persists across app restarts.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        tree = ttk.Treeview(
            frame,
            columns=("time", "action", "items", "status"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("time", text="Date")
        tree.heading("action", text="Action")
        tree.heading("items", text="Files")
        tree.heading("status", text="Status")
        tree.column("time", width=170, anchor="w")
        tree.column("action", width=280, anchor="w")
        tree.column("items", width=80, anchor="center")
        tree.column("status", width=110, anchor="center")
        tree.pack(fill="both", expand=True)

        transactions: dict[str, HistoryTransaction] = {}

        def refresh() -> None:
            for row in tree.get_children():
                tree.delete(row)
            transactions.clear()
            for transaction in self.history.recent(100):
                created = datetime.fromtimestamp(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")
                iid = transaction.transaction_id
                transactions[iid] = transaction
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        created,
                        transaction.label,
                        transaction.item_count,
                        "UNDONE" if transaction.is_undone else "APPLIED",
                    ),
                )

        def selected_transaction() -> HistoryTransaction | None:
            selection = tree.selection()
            return transactions.get(selection[0]) if selection else None

        def show_details() -> None:
            transaction = selected_transaction()
            if transaction is None:
                return
            self._show_report("History details", self._transaction_summary(transaction))

        def undo_selected() -> None:
            transaction = selected_transaction()
            if transaction is None:
                return
            self._undo_transaction(transaction)
            refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Details", command=show_details).pack(side="left")
        ttk.Button(buttons, text="Undo selected", command=undo_selected).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()

    # -------------------------------------------------------------- health
    def _show_library_health(self) -> None:
        records = list(self._all_records)
        statuses = Counter(record.view.status for record in records)
        total_size = sum(record.view.size or 0 for record in records)
        duplicate_groups = len(self._duplicate_groups)
        duplicate_files = sum(len(group) for group in self._duplicate_groups.values())
        cache_stats = self.cache.stats()

        lines = [
            "PS5 FFPFSC RENAMER — LIBRARY HEALTH",
            "",
            f"Scanned results: {len(records)}",
            f"Total FFPFSC size: {human_size(total_size)}",
            f"Library roots: {len(self.library_roots)}",
        ]
        for root in self.library_roots:
            lines.append(f"  {'OK' if root.is_dir() else 'MISSING'}  {root}")

        lines.extend(("", "Status summary:"))
        for status in ("READY", "UNCHANGED", "PARTIAL", "COLLISION", "INVALID", "ERROR"):
            lines.append(f"  {status}: {statuses.get(status, 0)}")
        lines.extend(
            (
                "",
                f"Duplicate Title ID groups: {duplicate_groups}",
                f"Files involved in duplicate groups: {duplicate_files}",
                "",
                "Cache:",
                f"  Verified metadata: {cache_stats.entries}",
                f"  Remembered unchanged failures: {cache_stats.failed_entries}",
                f"  SQLite footprint: {human_size(cache_stats.database_bytes)}",
                "",
                f"Rename history transactions: {self.history.count()}",
                f"MkPFS source: {mkpfs_source_description()}",
            )
        )
        if self._last_unavailable_roots:
            lines.extend(("", "Skipped roots from last scan:"))
            lines.extend(f"  {item}" for item in self._last_unavailable_roots)

        if statuses.get("ERROR", 0) or statuses.get("PARTIAL", 0):
            lines.extend(
                (
                    "",
                    "Recommendation: use Tools > Re-analyze PARTIAL / ERROR after updating MkPFS "
                    "or when you believe a problematic image has changed.",
                )
            )
        elif records:
            lines.extend(("", "Assessment: no current PARTIAL or ERROR rows were detected."))
        else:
            lines.extend(("", "Assessment: scan the library first to populate this report."))

        self._show_report("Library health", "\n".join(lines))

    # ------------------------------------------------------- cache manager
    def _show_cache_manager(self) -> None:
        window = tk.Toplevel(self)
        window.title("Cache Manager")
        window.transient(self)
        window.geometry("650x330")
        window.minsize(560, 300)

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Metadata cache", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Verified metadata and unchanged MkPFS failures are stored separately in the same SQLite database.",
            style="CardMuted.TLabel",
            wraplength=600,
        ).pack(anchor="w", pady=(2, 10))

        info_var = tk.StringVar()
        path_var = tk.StringVar(value=str(self.cache.db_path))
        ttk.Label(frame, textvariable=info_var, style="Card.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(frame, textvariable=path_var, style="CardMuted.TLabel", wraplength=600).pack(anchor="w")

        def refresh() -> None:
            stats = self.cache.stats()
            info_var.set(
                f"Verified: {stats.entries}     Remembered errors: {stats.failed_entries}     "
                f"Disk: {human_size(stats.database_bytes)}"
            )
            self.cache_entries_var.set(str(stats.entries))

        def prune() -> None:
            if self._scan_active:
                messagebox.showinfo("Cache Manager", "Wait for the current scan to finish first.", parent=window)
                return
            try:
                removed = self.cache.prune_missing()
            except Exception as exc:
                messagebox.showerror("Cache Manager", str(exc), parent=window)
                return
            refresh()
            messagebox.showinfo("Cache Manager", f"Removed {removed} stale cache record(s).", parent=window)

        def compact() -> None:
            if self._scan_active:
                messagebox.showinfo("Cache Manager", "Wait for the current scan to finish first.", parent=window)
                return
            try:
                self.cache.vacuum()
            except Exception as exc:
                messagebox.showerror("Cache Manager", str(exc), parent=window)
                return
            refresh()
            messagebox.showinfo("Cache Manager", "SQLite cache compacted.", parent=window)

        def clear_all() -> None:
            if self._scan_active:
                return
            if not messagebox.askyesno(
                "Clear metadata cache",
                "Delete all verified metadata and remembered error cache entries?\n\n"
                "The next scan will ask MkPFS to inspect every file again.",
                parent=window,
            ):
                return
            self.cache.clear()
            self.cached_var.set("0")
            refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Prune missing", command=prune).pack(side="left")
        ttk.Button(buttons, text="Compact DB", command=compact).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Clear all...", command=clear_all).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons,
            text="Open folder",
            command=lambda: self._open_folder(self.cache.db_path),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()

    # ------------------------------------------------------------ MkPFS UI
    def _show_mkpfs_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("MkPFS engine")
        window.transient(self)
        window.geometry("760x350")
        window.minsize(620, 320)

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MkPFS engine", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="The packaged app normally uses its sibling mkpfs-helper.exe. You can optionally point the renamer at another compatible MkPFS executable for testing/upgrades.",
            style="CardMuted.TLabel",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 10))

        source_var = tk.StringVar()
        ttk.Label(frame, text="Current source", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=source_var, style="Card.TLabel", wraplength=710).pack(anchor="w", pady=(2, 12))

        def refresh() -> None:
            source_var.set(mkpfs_source_description())

        def choose() -> None:
            selected = filedialog.askopenfilename(
                title="Select MkPFS executable",
                parent=window,
                filetypes=(("Executable files", "*.exe"), ("All files", "*.*")),
            )
            if not selected:
                return
            selected_path = Path(selected).resolve()
            if not selected_path.is_file():
                return
            self._mkpfs_path = str(selected_path)
            set_mkpfs_executable(selected_path)
            self._queue_save_preferences()
            refresh()

        def automatic() -> None:
            self._mkpfs_path = None
            set_mkpfs_executable(None)
            self._queue_save_preferences()
            refresh()

        def test_engine() -> None:
            try:
                command = [*_mkpfs_command(), "--help"]
                completed = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15,
                    check=False,
                )
                output = "\n".join(
                    part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
                )
                if completed.returncode == 0:
                    messagebox.showinfo(
                        "MkPFS test",
                        "MkPFS launched successfully.\n\n" + (output[:1200] or "No output."),
                        parent=window,
                    )
                else:
                    messagebox.showwarning(
                        "MkPFS test",
                        f"MkPFS returned code {completed.returncode}.\n\n{output[:1600]}",
                        parent=window,
                    )
            except Exception as exc:
                messagebox.showerror("MkPFS test", str(exc), parent=window)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Choose executable...", command=choose).pack(side="left")
        ttk.Button(buttons, text="Use automatic / bundled", command=automatic).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Test engine", command=test_engine).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()

    # -------------------------------------------------------------- misc
    def _select_all_rows(self) -> None:
        rows = self.tree.get_children()
        if rows:
            self.tree.selection_set(rows)
            self.status_var.set(f"Selected {len(rows)} visible result(s)")

    def _open_app_data_folder(self) -> None:
        folder = self.cache.db_path.parent
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About PS5 FFPFSC Renamer",
            f"PS5 FFPFSC Renamer v{__version__}\n\n"
            "Created by XaRaBaS\n"
            "https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer\n\n"
            "Homebrew & Personal Backup Tool\n"
            "For games/content you legally own and dumped yourself. The software does not download games, decrypt retail packages, bypass DRM or provide copyrighted content.\n\n"
            f"MkPFS: {mkpfs_source_description()}",
            parent=self,
        )


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
