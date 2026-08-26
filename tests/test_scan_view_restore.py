from __future__ import annotations

import pytest

from ps5_ffpfsc_renamer.renamer import RenameTransactionError
from ps5_ffpfsc_renamer.ui.rename_safety_mixin import RenameSafetyMixin
from ps5_ffpfsc_renamer.ui.scan_view_restore_mixin import ScanViewRestoreMixin


class _Var:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Button:
    def __init__(self) -> None:
        self.state = "normal"

    def configure(self, **kwargs) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class _BaseScanHarness:
    def __init__(self) -> None:
        self._scan_active = False
        self.parsed_items = ["old-parsed"]
        self.scan_errors = ["old-error"]
        self.partial_items = ["old-partial"]
        self.plan = ["old-plan"]
        self._all_records = []
        self._last_scan_file_states = {"old-path": "old-state"}
        self.files_var = _Var("11")
        self.cached_var = _Var("7")
        self.ready_var = _Var("3")
        self.blocked_var = _Var("1")
        self.status_var = _Var("old status")
        self.progress_note_var = _Var("old note")
        self.progress_detail_var = _Var("old detail")
        self.last_scan_total = 11
        self.last_cache_hits = 7
        self.last_mkpfs_reads = 4
        self.last_scan_elapsed = 12.5
        self.last_worker_count = 2
        self._last_failure_cache_hits = 1
        self._last_batch_cache_files = 11
        self._last_collapsed_root_count = 2
        self._root_statuses = {"old": "online"}
        self._last_unavailable_roots = ()
        self.rename_button = _Button()
        self.render_count = 0

    def _render_records(self) -> None:
        self.render_count += 1

    def _scan(self) -> None:
        self.parsed_items = []
        self.scan_errors = []
        self.partial_items = []
        self.plan = []
        self._all_records = []
        self._last_scan_file_states = {"partial-path": "partial-state"}
        self.files_var.set("0")
        self.cached_var.set("0")
        self.ready_var.set("0")
        self.blocked_var.set("0")
        self._root_statuses = {"offline": "unavailable"}
        self._last_unavailable_roots = ("offline",)
        self._scan_active = True

    def _scan_failed(self, detail: str) -> None:
        self._scan_active = False
        self.plan = []
        self.blocked_var.set("1")
        self.status_var.set("Scan failed")
        self.progress_note_var.set("The scan stopped because an error occurred.")
        self.progress_detail_var.set(detail)

    def _scan_cancelled(self, completed: int, total: int) -> None:
        self._scan_active = False
        self.plan = []
        self.status_var.set(f"Cancelled — {completed}/{total} processed")
        self.progress_note_var.set("Analysis cancelled.")
        self.progress_detail_var.set(f"Stopped after {completed}/{total}")

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
        self._scan_active = False
        self.parsed_items = list(parsed)
        self.scan_errors = list(errors)
        self.partial_items = []
        self.plan = ["new-plan"]
        self._all_records = []
        self._last_scan_file_states = {"new-path": "fresh-state"}
        self.files_var.set(str(total))
        self.cached_var.set(str(cache_hits))
        self.ready_var.set("1")
        self.blocked_var.set("0")


class _ScanHarness(ScanViewRestoreMixin, _BaseScanHarness):
    pass


def test_failed_scan_restores_previous_results_but_keeps_new_root_state() -> None:
    harness = _ScanHarness()

    harness._scan()
    assert harness.parsed_items == []
    assert harness._scan_view_snapshot is not None

    harness._scan_failed("NAS unavailable")

    assert harness.parsed_items == ["old-parsed"]
    assert harness.scan_errors == ["old-error"]
    assert harness.partial_items == ["old-partial"]
    assert harness.plan == ["old-plan"]
    assert harness._last_scan_file_states == {"old-path": "old-state"}
    assert harness.files_var.get() == "11"
    assert harness.cached_var.get() == "7"
    assert harness.ready_var.get() == "3"
    assert harness.blocked_var.get() == "1"
    assert harness._root_statuses == {"offline": "unavailable"}
    assert harness._last_unavailable_roots == ("offline",)
    assert harness.progress_detail_var.get() == "NAS unavailable"
    assert "previous library results preserved" in harness.status_var.get()
    assert "automatic rename is disabled" in harness.progress_note_var.get()
    assert harness.rename_button.state == "disabled"
    assert harness._scan_view_stale is True
    assert harness._scan_view_snapshot is None
    assert harness.render_count == 1


def test_cancelled_scan_restores_previous_results_as_stale() -> None:
    harness = _ScanHarness()

    harness._scan()
    harness._scan_cancelled(4, 11)

    assert harness.parsed_items == ["old-parsed"]
    assert harness.plan == ["old-plan"]
    assert harness.progress_detail_var.get() == "Stopped after 4/11"
    assert "previous library results preserved" in harness.status_var.get()
    assert harness.rename_button.state == "disabled"
    assert harness._scan_view_stale is True


def test_successful_scan_discards_snapshot_and_marks_view_fresh() -> None:
    harness = _ScanHarness()
    harness._scan_view_stale = True

    harness._scan()
    harness._scan_complete(["new-parsed"], [], 1, 0.0, 1, 0, 1)

    assert harness.parsed_items == ["new-parsed"]
    assert harness.plan == ["new-plan"]
    assert harness._last_scan_file_states == {"new-path": "fresh-state"}
    assert harness._scan_view_snapshot is None
    assert harness._scan_view_stale is False


def test_stale_view_blocks_automatic_rename_before_preflight() -> None:
    class _SafetyHarness:
        _require_fresh_scan_view = RenameSafetyMixin._require_fresh_scan_view
        _scan_view_stale = True

    with pytest.raises(RenameTransactionError, match="previous successful scan"):
        _SafetyHarness()._require_fresh_scan_view()


def test_fresh_view_allows_automatic_rename_preflight_to_continue() -> None:
    class _SafetyHarness:
        _require_fresh_scan_view = RenameSafetyMixin._require_fresh_scan_view
        _scan_view_stale = False

    _SafetyHarness()._require_fresh_scan_view()
