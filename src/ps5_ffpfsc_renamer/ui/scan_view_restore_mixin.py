from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _ScanViewSnapshot:
    parsed_items: list[Any]
    scan_errors: list[Any]
    partial_items: list[Any]
    plan: list[Any]
    all_records: list[Any]
    last_scan_file_states: dict[Any, Any]
    files_value: str
    cached_value: str
    ready_value: str
    blocked_value: str
    last_scan_total: int
    last_cache_hits: int
    last_mkpfs_reads: int
    last_scan_elapsed: float
    last_worker_count: int
    last_failure_cache_hits: int
    last_batch_cache_files: int
    last_collapsed_root_count: int


class ScanViewRestoreMixin:
    """Preserve the last successful library view across failed/cancelled scans.

    A restored view is deliberately marked stale. It remains useful for
    inspection, search and reporting, but automatic rename plans must not be
    applied until a later scan completes successfully.
    """

    def __init__(self) -> None:
        self._scan_view_snapshot: _ScanViewSnapshot | None = None
        self._scan_view_stale = False
        super().__init__()

    @staticmethod
    def _var_text(owner: Any, name: str, default: str = "0") -> str:
        variable = getattr(owner, name, None)
        if variable is None:
            return default
        try:
            return str(variable.get())
        except Exception:
            return default

    def _capture_scan_view(self) -> _ScanViewSnapshot | None:
        parsed = list(getattr(self, "parsed_items", []))
        errors = list(getattr(self, "scan_errors", []))
        partial = list(getattr(self, "partial_items", []))
        plan = list(getattr(self, "plan", []))
        records = list(getattr(self, "_all_records", []))
        if not (parsed or errors or partial or plan or records):
            return None

        return _ScanViewSnapshot(
            parsed_items=parsed,
            scan_errors=errors,
            partial_items=partial,
            plan=plan,
            all_records=records,
            last_scan_file_states=dict(getattr(self, "_last_scan_file_states", {})),
            files_value=self._var_text(self, "files_var"),
            cached_value=self._var_text(self, "cached_var"),
            ready_value=self._var_text(self, "ready_var"),
            blocked_value=self._var_text(self, "blocked_var"),
            last_scan_total=int(getattr(self, "last_scan_total", 0)),
            last_cache_hits=int(getattr(self, "last_cache_hits", 0)),
            last_mkpfs_reads=int(getattr(self, "last_mkpfs_reads", 0)),
            last_scan_elapsed=float(getattr(self, "last_scan_elapsed", 0.0)),
            last_worker_count=int(getattr(self, "last_worker_count", 1)),
            last_failure_cache_hits=int(getattr(self, "_last_failure_cache_hits", 0)),
            last_batch_cache_files=int(getattr(self, "_last_batch_cache_files", 0)),
            last_collapsed_root_count=int(getattr(self, "_last_collapsed_root_count", 0)),
        )

    def _scan(self) -> None:
        if not getattr(self, "_scan_active", False):
            self._scan_view_snapshot = self._capture_scan_view()
        super()._scan()
        # Validation can reject a scan before any worker starts. In that case
        # no failure/cancel callback will arrive, so discard the temporary copy.
        if not getattr(self, "_scan_active", False):
            self._scan_view_snapshot = None

    def _restore_previous_scan_view(self) -> bool:
        snapshot = self._scan_view_snapshot
        self._scan_view_snapshot = None
        if snapshot is None:
            self._scan_view_stale = False
            return False

        self.parsed_items = list(snapshot.parsed_items)
        self.scan_errors = list(snapshot.scan_errors)
        self.partial_items = list(snapshot.partial_items)
        self.plan = list(snapshot.plan)
        self._all_records = list(snapshot.all_records)
        self._last_scan_file_states = dict(snapshot.last_scan_file_states)
        self.last_scan_total = snapshot.last_scan_total
        self.last_cache_hits = snapshot.last_cache_hits
        self.last_mkpfs_reads = snapshot.last_mkpfs_reads
        self.last_scan_elapsed = snapshot.last_scan_elapsed
        self.last_worker_count = snapshot.last_worker_count
        self._last_failure_cache_hits = snapshot.last_failure_cache_hits
        self._last_batch_cache_files = snapshot.last_batch_cache_files
        self._last_collapsed_root_count = snapshot.last_collapsed_root_count

        for name, value in (
            ("files_var", snapshot.files_value),
            ("cached_var", snapshot.cached_value),
            ("ready_var", snapshot.ready_value),
            ("blocked_var", snapshot.blocked_value),
        ):
            variable = getattr(self, name, None)
            if variable is not None:
                try:
                    variable.set(value)
                except Exception:
                    pass

        self._duplicate_groups = {}
        for record in self._all_records:
            try:
                view = record.view
            except AttributeError:
                continue
            if getattr(view, "duplicate", False) and getattr(view, "title_id", "-") != "-":
                self._duplicate_groups.setdefault(view.title_id.upper(), []).append(record)

        try:
            self._render_records()
        except Exception:
            pass

        # A preserved view may no longer match the filesystem. Keep it useful
        # for inspection but never present its old automatic plan as actionable.
        rename_button = getattr(self, "rename_button", None)
        if rename_button is not None:
            try:
                rename_button.configure(state="disabled")
            except Exception:
                pass

        self._scan_view_stale = True
        return True

    def _scan_failed(self, detail: str) -> None:
        super()._scan_failed(detail)
        if self._restore_previous_scan_view():
            try:
                self.status_var.set("Scan failed — previous library results preserved")
                self.progress_note_var.set(
                    "The scan failed. Results from the previous successful scan remain visible for inspection; "
                    "automatic rename is disabled until a scan completes successfully."
                )
            except Exception:
                pass

    def _scan_cancelled(self, completed: int, total: int) -> None:
        super()._scan_cancelled(completed, total)
        if self._restore_previous_scan_view():
            try:
                self.status_var.set("Scan cancelled — previous library results preserved")
                self.progress_note_var.set(
                    "The scan was cancelled. Results from the previous successful scan remain visible for inspection; "
                    "automatic rename is disabled until a scan completes successfully."
                )
            except Exception:
                pass

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
        self._scan_view_snapshot = None
        self._scan_view_stale = False
