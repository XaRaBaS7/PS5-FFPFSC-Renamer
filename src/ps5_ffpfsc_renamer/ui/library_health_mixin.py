from __future__ import annotations

from collections import Counter
import tkinter as tk
from tkinter import ttk

from ..ffpfsc_reader import mkpfs_source_description
from ..library_view import human_size


class LibraryHealthMixin:
    """Library health report with direct non-destructive remediation actions."""

    FILTERS = (
        "ALL",
        "HEALTHY",
        "PROBLEMS",
        "READY",
        "UNCHANGED",
        "PARTIAL",
        "COLLISION",
        "INVALID",
        "ERROR",
        "ADDED",
        "CHANGED",
        "DUPLICATES",
    )

    def _focus_health_filter(self, filter_name: str) -> None:
        """Focus the main table on a health-oriented result subset."""
        if filter_name not in self.FILTERS:
            raise ValueError(f"Unsupported health filter: {filter_name}")
        if hasattr(self, "search_var"):
            self.search_var.set("")
        if hasattr(self, "filter_var"):
            self.filter_var.set(filter_name)
        self._render_records()
        if hasattr(self, "status_var"):
            self.status_var.set(f"Library view: {filter_name}")

    def _show_health_report(
        self,
        text: str,
        *,
        has_problems: bool,
        has_duplicates: bool,
        can_reanalyze: bool,
    ) -> None:
        window = tk.Toplevel(self)
        window.title("Library health")
        window.transient(self)
        window.geometry("960x650")
        window.minsize(760, 520)

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
        ttk.Button(
            buttons,
            text="Copy report",
            command=lambda: self._copy_text(text),
        ).pack(side="left")

        if has_problems:
            ttk.Button(
                buttons,
                text="Show problems",
                command=lambda: self._focus_health_filter("PROBLEMS"),
            ).pack(side="left", padx=(6, 0))
        if has_duplicates:
            ttk.Button(
                buttons,
                text="Show duplicates",
                command=lambda: self._focus_health_filter("DUPLICATES"),
            ).pack(side="left", padx=(6, 0))
        if can_reanalyze:
            ttk.Button(
                buttons,
                text="Re-analyze PARTIAL / ERROR...",
                command=self._reanalyze_problem_rows,
            ).pack(side="left", padx=(6, 0))
        if self.library_roots:
            ttk.Button(
                buttons,
                text="Manage roots...",
                command=self._manage_folders,
            ).pack(side="left", padx=(6, 0))

        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

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
            status = self._root_status(root) if hasattr(self, "_root_status") else None
            state = status.state if status is not None else "UNKNOWN"
            detail = f" — {status.detail}" if status is not None and status.detail else ""
            lines.append(f"  {state:<7}  {root}{detail}")

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

        profile = getattr(self, "_last_scan_profile", None)
        if profile is not None:
            lines.extend(
                (
                    "",
                    "Last scan performance:",
                    f"  Root availability: {profile.root_probe_seconds:.3f}s",
                    f"  File discovery: {profile.discovery_seconds:.3f}s",
                    f"  Cache lookup: {profile.cache_seconds:.3f}s",
                    f"  MkPFS reads: {profile.mkpfs_seconds:.3f}s",
                    f"  Total: {profile.total_seconds:.3f}s",
                    f"  Cache hit ratio: {profile.cache_hit_ratio:.1%}",
                    f"  Throughput: {profile.files_per_second:.1f} file(s)/s",
                    f"  Effective roots: {profile.effective_roots}/{profile.selected_roots}",
                )
            )

        collapsed = int(getattr(self, "_last_collapsed_root_count", 0) or 0)
        if collapsed:
            lines.append(f"Nested roots skipped during last recursive scan: {collapsed}")

        diff = getattr(self, "_last_scan_diff", None)
        if diff is not None:
            lines.extend(
                (
                    "",
                    "Changes since previous successful scan:",
                    f"  Added: {len(diff.added)}",
                    f"  Removed: {len(diff.removed)}",
                    f"  Changed: {len(diff.changed)}",
                    f"  Root selection changed: {'yes' if diff.roots_changed else 'no'}",
                )
            )

        unavailable = tuple(getattr(self, "_last_unavailable_roots", ()))
        if unavailable:
            lines.extend(("", "Skipped roots from last scan:"))
            lines.extend(f"  {item}" for item in unavailable)

        if statuses.get("ERROR", 0) or statuses.get("PARTIAL", 0):
            lines.extend(
                (
                    "",
                    "Recommendation: use Re-analyze PARTIAL / ERROR after updating MkPFS "
                    "or when a problematic image is believed to have changed.",
                )
            )
        elif unavailable:
            lines.extend(
                (
                    "",
                    "Assessment: scanned files are healthy, but one or more selected roots were unavailable.",
                )
            )
        elif records:
            lines.extend(("", "Assessment: no current PARTIAL or ERROR rows were detected."))
        else:
            lines.extend(("", "Assessment: scan the library first to populate this report."))

        problem_count = sum(
            statuses.get(status, 0)
            for status in ("PARTIAL", "COLLISION", "INVALID", "ERROR")
        )
        self._show_health_report(
            "\n".join(lines),
            has_problems=problem_count > 0,
            has_duplicates=duplicate_files > 0,
            can_reanalyze=bool(statuses.get("PARTIAL", 0) or statuses.get("ERROR", 0)),
        )
