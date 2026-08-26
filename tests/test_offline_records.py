from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.offline_records import (
    merge_preserved_offline_records,
    records_from_scan_snapshot,
)
from ps5_ffpfsc_renamer.root_health import RootStatus, root_key
from ps5_ffpfsc_renamer.scan_snapshot import build_scan_snapshot
from ps5_ffpfsc_renamer.workspace_models import LibraryRecord


def _record(path: Path, *, title_id: str, status: str = "READY", plan_item=None) -> LibraryRecord:
    return LibraryRecord(
        ResultRow(
            source=path,
            title_id=title_id,
            title=path.stem,
            version="1.0",
            size=123,
            output=f"renamed-{path.name}",
            status=status,
        ),
        plan_item=plan_item,
    )


def test_offline_root_previous_rows_are_preserved_read_only(tmp_path: Path) -> None:
    online_root = tmp_path / "online"
    offline_root = tmp_path / "offline"
    current = _record(online_root / "fresh.ffpfsc", title_id="PPSA00001", plan_item="fresh-plan")
    previous_offline = _record(offline_root / "old.ffpfsc", title_id="PPSA00002", plan_item="old-plan")
    statuses = {
        root_key(online_root): RootStatus(online_root, "ONLINE", "available"),
        root_key(offline_root): RootStatus(offline_root, "OFFLINE", "unavailable"),
    }

    merged, preserved = merge_preserved_offline_records(
        [current],
        [previous_offline],
        roots=[online_root, offline_root],
        statuses=statuses,
    )

    assert len(merged) == 2
    assert merged[0].view.status == "READY"
    assert merged[0].plan_item == "fresh-plan"
    offline = merged[1]
    assert offline.view.source == previous_offline.view.source
    assert offline.view.status == "OFFLINE"
    assert offline.view.output == "-"
    assert offline.view.change == ""
    assert offline.plan_item is None
    assert "previous successful scan" in offline.friendly
    assert preserved == (previous_offline.view.source,)


def test_missing_row_under_online_root_is_not_preserved(tmp_path: Path) -> None:
    root = tmp_path / "online"
    previous = _record(root / "deleted.ffpfsc", title_id="PPSA00001")

    merged, preserved = merge_preserved_offline_records(
        [],
        [previous],
        roots=[root],
        statuses={root_key(root): RootStatus(root, "ONLINE", "available")},
    )

    assert merged == []
    assert preserved == ()


def test_row_from_removed_root_is_not_preserved(tmp_path: Path) -> None:
    configured = tmp_path / "configured"
    removed = tmp_path / "removed"
    previous = _record(removed / "old.ffpfsc", title_id="PPSA00001")

    merged, preserved = merge_preserved_offline_records(
        [],
        [previous],
        roots=[configured],
        statuses={root_key(configured): RootStatus(configured, "ONLINE", "available")},
    )

    assert merged == []
    assert preserved == ()


def test_current_scan_result_wins_over_previous_offline_copy(tmp_path: Path) -> None:
    root = tmp_path / "root"
    path = root / "game.ffpfsc"
    current = _record(path, title_id="PPSA00001", status="READY", plan_item="fresh")
    previous = _record(path, title_id="PPSA00001", status="READY", plan_item="old")

    merged, preserved = merge_preserved_offline_records(
        [current],
        [previous],
        roots=[root],
        statuses={root_key(root): RootStatus(root, "OFFLINE", "temporarily unavailable")},
    )

    assert len(merged) == 1
    assert merged[0].plan_item == "fresh"
    assert merged[0].view.status == "READY"
    assert preserved == ()


def test_duplicate_state_is_recomputed_across_fresh_and_offline_rows(tmp_path: Path) -> None:
    online_root = tmp_path / "online"
    offline_root = tmp_path / "offline"
    current = _record(online_root / "a.ffpfsc", title_id="PPSA00001")
    previous = _record(offline_root / "b.ffpfsc", title_id="ppsa00001")

    merged, _ = merge_preserved_offline_records(
        [current],
        [previous],
        roots=[online_root, offline_root],
        statuses={
            root_key(online_root): RootStatus(online_root, "ONLINE", "available"),
            root_key(offline_root): RootStatus(offline_root, "OFFLINE", "unavailable"),
        },
    )

    assert [record.view.duplicate for record in merged] == [True, True]


def test_persisted_snapshot_can_seed_offline_display_rows(tmp_path: Path) -> None:
    image = tmp_path / "archive" / "game.ffpfsc"
    snapshot = build_scan_snapshot(
        [_record(image, title_id="PPSA01285").view],
        roots=[tmp_path / "archive"],
        created_at=10,
    )

    records = records_from_scan_snapshot(snapshot)

    assert len(records) == 1
    assert records[0].view.source == image
    assert records[0].view.title_id == "PPSA01285"
    assert records[0].view.status == "READY"
    assert records[0].view.output == "-"
    assert records[0].plan_item is None
