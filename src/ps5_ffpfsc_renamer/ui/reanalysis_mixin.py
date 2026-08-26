from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox

from ..diagnostics import classify_reader_error, infer_metadata_from_path
from ..ffpfsc_reader import MetadataReadError, read_metadata
from ..metadata import GameMetadata


class ReanalysisMixin:
    """Force fresh MkPFS analysis for selected PARTIAL/ERROR rows."""

    def _analyze_paths(self, paths: list[Path]) -> None:
        if self._scan_active:
            messagebox.showinfo(
                "Analyze again",
                "Wait for the current library scan to finish first.",
                parent=self,
            )
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
            messagebox.showinfo(
                "Re-analyze",
                "There are no PARTIAL or ERROR rows in the current library.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Re-analyze problematic files",
            f"Force MkPFS to analyze {len(problem_paths)} PARTIAL/ERROR file(s) again?\n\n"
            "This bypasses the cached previous error for these files.",
            parent=self,
        ):
            return
        self._analyze_paths(problem_paths)
