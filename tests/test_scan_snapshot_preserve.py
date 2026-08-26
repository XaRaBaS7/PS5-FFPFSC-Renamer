from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.scan_snapshot import build_scan_snapshot, compare_scan_snapshots
from ps5_ffpfsc_renamer.scan_snapshot_preserve import carry_forward_preserved_entries


def _row(path: Path, *, version: str = "1.0", status: str = "READY") -> ResultRow:
    return ResultRow(
        source=path,
        title_id="PPSA00001",
        title="Game",
        version=version,
        size=123,
        output="Game.ffpfsc",
        status=status,
    )


def test_preserved_offline_entry_does_not_create_false_removed_or_changed(tmp_path: Path) -> None:
    online = tmp_path / "online.ffpfsc"
    offline = tmp_path / "offline.ffpfsc"
    previous = build_scan_snapshot(
        [_row(online), _row(offline, version="1.2")],
        roots=[tmp_path],
        created_at=10,
    )
    current = build_scan_snapshot(
        [_row(online)],
        roots=[tmp_path],
        created_at=20,
    )

    carried = carry_forward_preserved_entries(previous, current, [offline])
    diff = compare_scan_snapshots(previous, carried)

    assert diff.added == ()
    assert diff.removed == ()
    assert diff.changed == ()


def test_non_preserved_missing_entry_remains_a_real_removal(tmp_path: Path) -> None:
    removed = tmp_path / "removed.ffpfsc"
    previous = build_scan_snapshot([_row(removed)], roots=[tmp_path], created_at=10)
    current = build_scan_snapshot([], roots=[tmp_path], created_at=20)

    carried = carry_forward_preserved_entries(previous, current, [])
    diff = compare_scan_snapshots(previous, carried)

    assert [Path(entry.path) for entry in diff.removed] == [removed]


def test_preserved_path_uses_previous_verified_entry_instead_of_offline_ui_state(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    previous = build_scan_snapshot(
        [_row(image, version="1.2", status="READY")],
        roots=[tmp_path],
        created_at=10,
    )
    current = build_scan_snapshot(
        [_row(image, version="1.2", status="OFFLINE")],
        roots=[tmp_path],
        created_at=20,
    )

    carried = carry_forward_preserved_entries(previous, current, [image])

    assert carried.entries[0].status == "READY"
    assert carried.entries[0].version == "1.2"
    assert compare_scan_snapshots(previous, carried).changed == ()
