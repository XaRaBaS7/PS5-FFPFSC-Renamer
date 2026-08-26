from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.ui.preserved_view_guard_mixin import PreservedViewGuardMixin
from ps5_ffpfsc_renamer.workspace_models import LibraryRecord


def _record(path: Path, status: str = "READY") -> LibraryRecord:
    return LibraryRecord(
        ResultRow(
            source=path,
            title_id="PPSA00001",
            title="Game",
            version="1.0",
            size=100,
            output="Game.ffpfsc",
            status=status,
        )
    )


class _BaseGuardHarness:
    def __init__(self) -> None:
        self._scan_view_stale = False
        self._all_records = []
        self._duplicate_groups = {}
        self.selected = []
        self.calls: list[str] = []
        self.notices: list[str] = []

    def _selected_records(self):
        return list(self.selected)

    def _prefetch_selected_details(self) -> None:
        self.calls.append("prefetch")

    def _run_diagnostics(self, path: Path) -> None:
        self.calls.append(f"diagnostics:{path}")

    def _analyze_paths(self, paths: list[Path]) -> None:
        self.calls.append("analyze")

    def _compare_duplicates(self, title_id: str) -> None:
        self.calls.append(f"compare:{title_id}")


class _GuardHarness(PreservedViewGuardMixin, _BaseGuardHarness):
    def _show_preserved_view_notice(self, title: str) -> None:
        self.notices.append(title)


def test_fresh_online_records_delegate_to_existing_actions(tmp_path: Path) -> None:
    path = tmp_path / "game.ffpfsc"
    record = _record(path)
    harness = _GuardHarness()
    harness._all_records = [record]
    harness.selected = [record]
    harness._duplicate_groups = {"PPSA00001": [record, _record(tmp_path / "copy.ffpfsc")]}

    harness._prefetch_selected_details()
    harness._run_diagnostics(path)
    harness._analyze_paths([path])
    harness._compare_duplicates("PPSA00001")

    assert harness.calls == [
        "prefetch",
        f"diagnostics:{path}",
        "analyze",
        "compare:PPSA00001",
    ]
    assert harness.notices == []


def test_whole_stale_view_blocks_filesystem_actions(tmp_path: Path) -> None:
    path = tmp_path / "game.ffpfsc"
    record = _record(path)
    harness = _GuardHarness()
    harness._scan_view_stale = True
    harness._all_records = [record]
    harness.selected = [record]
    harness._duplicate_groups = {"PPSA00001": [record, _record(tmp_path / "copy.ffpfsc")]}

    harness._prefetch_selected_details()
    harness._run_diagnostics(path)
    harness._analyze_paths([path])
    harness._compare_duplicates("PPSA00001")

    assert harness.calls == []
    assert harness.notices == [
        "Preload game details",
        "Diagnostics",
        "Analyze again",
        "Compare duplicates",
    ]


def test_offline_record_blocks_path_and_duplicate_io_without_staling_online_rows(tmp_path: Path) -> None:
    online = _record(tmp_path / "online.ffpfsc")
    offline = _record(tmp_path / "offline.ffpfsc", status="OFFLINE")
    harness = _GuardHarness()
    harness._all_records = [online, offline]
    harness._duplicate_groups = {"PPSA00001": [online, offline]}

    assert harness._record_requires_live_filesystem(online) is False
    assert harness._record_requires_live_filesystem(offline) is True
    assert harness._path_requires_live_filesystem(online.view.source) is False
    assert harness._path_requires_live_filesystem(offline.view.source) is True

    harness._run_diagnostics(online.view.source)
    harness._run_diagnostics(offline.view.source)
    harness._compare_duplicates("PPSA00001")

    assert harness.calls == [f"diagnostics:{online.view.source}"]
    assert harness.notices == ["Diagnostics", "Compare duplicates"]


def test_mixed_selection_blocks_prefetch_when_any_row_is_offline(tmp_path: Path) -> None:
    online = _record(tmp_path / "online.ffpfsc")
    offline = _record(tmp_path / "offline.ffpfsc", status="OFFLINE")
    harness = _GuardHarness()
    harness._all_records = [online, offline]
    harness.selected = [online, offline]

    harness._prefetch_selected_details()

    assert harness.calls == []
    assert harness.notices == ["Preload game details"]
