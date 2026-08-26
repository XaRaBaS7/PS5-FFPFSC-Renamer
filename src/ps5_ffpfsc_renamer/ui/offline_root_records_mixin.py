from __future__ import annotations

from ..offline_records import merge_preserved_offline_records, records_from_scan_snapshot


class OfflineRootRecordsMixin:
    """Keep previous metadata visible for configured roots skipped as unavailable."""

    def __init__(self) -> None:
        self._offline_preserved_paths: frozenset[str] = frozenset()
        self._last_offline_preserved_count = 0
        super().__init__()

    def _render_records(self) -> None:
        super()._render_records()
        for row, record in getattr(self, "_row_records", {}).items():
            if record.view.status.upper() != "OFFLINE":
                continue
            self._row_tooltips[row] = (
                "OFFLINE\n"
                "This row was preserved from the previous successful scan because its library root "
                "is currently unavailable. Filesystem actions are disabled until that root is scanned again."
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
        view_snapshot = getattr(self, "_scan_view_snapshot", None)
        previous_baseline = getattr(self, "_scan_snapshot", None)

        super()._scan_complete(
            parsed,
            errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )

        previous_records = []
        if view_snapshot is not None:
            previous_records.extend(view_snapshot.all_records)
        previous_records.extend(records_from_scan_snapshot(previous_baseline))

        combined, preserved_paths = merge_preserved_offline_records(
            getattr(self, "_all_records", ()),
            previous_records,
            roots=getattr(self, "library_roots", ()),
            statuses=getattr(self, "_root_statuses", {}),
        )
        self._offline_preserved_paths = frozenset(
            str(path).casefold() for path in preserved_paths
        )
        self._last_offline_preserved_count = len(preserved_paths)
        if not preserved_paths:
            return

        self._all_records = combined
        self._duplicate_groups = {}
        for record in self._all_records:
            if record.view.duplicate and record.view.title_id != "-":
                self._duplicate_groups.setdefault(record.view.title_id.upper(), []).append(record)
        self._render_records()

        note = (
            f"{len(preserved_paths)} result(s) from unavailable root(s) were preserved as OFFLINE "
            "from the previous successful scan."
        )
        try:
            self.progress_note_var.set(self.progress_note_var.get() + " " + note)
            self.status_var.set(self.status_var.get() + f" • {len(preserved_paths)} offline preserved")
            self._log("WARN", note)
        except Exception:
            pass
