from pathlib import Path

from ps5_ffpfsc_renamer.cache_batch import FileState
from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.scan_snapshot import (
    build_scan_snapshot,
    compare_scan_snapshots,
    load_scan_snapshot,
    migrate_snapshot_paths,
    save_scan_snapshot,
)


def _row(path: Path, *, status: str = "READY", version: str = "1.0", duplicate: bool = False) -> ResultRow:
    return ResultRow(
        source=path,
        title_id="PPSA01285",
        title="Returnal",
        version=version,
        size=123,
        output="PPSA01285.ffpfsc",
        status=status,
        duplicate=duplicate,
    )


def test_scan_snapshot_round_trip(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    row = _row(image)
    state = FileState(size=987, mtime_ns=123456789)
    snapshot = build_scan_snapshot(
        [row],
        roots=[tmp_path],
        file_states={image: state},
        created_at=100,
    )
    path = tmp_path / "snapshot.json"

    save_scan_snapshot(snapshot, path)
    loaded = load_scan_snapshot(path)

    assert loaded == snapshot
    assert loaded is not None
    assert loaded.entries[0].size == 987
    assert loaded.entries[0].mtime_ns == 123456789


def test_scan_diff_detects_added_removed_and_changed(tmp_path: Path) -> None:
    kept = tmp_path / "kept.ffpfsc"
    removed = tmp_path / "removed.ffpfsc"
    added = tmp_path / "added.ffpfsc"

    previous = build_scan_snapshot(
        [_row(kept, version="1.0"), _row(removed)],
        roots=[tmp_path],
        file_states={
            kept: FileState(100, 10),
            removed: FileState(200, 20),
        },
        created_at=10,
    )
    current = build_scan_snapshot(
        [_row(kept, version="1.1"), _row(added)],
        roots=[tmp_path],
        file_states={
            kept: FileState(100, 11),
            added: FileState(300, 30),
        },
        created_at=20,
    )

    diff = compare_scan_snapshots(previous, current)

    assert [Path(item.path).name for item in diff.added] == ["added.ffpfsc"]
    assert [Path(item.path).name for item in diff.removed] == ["removed.ffpfsc"]
    assert len(diff.changed) == 1
    assert diff.changed[0].after.path == str(kept)
    assert "modified time" in diff.changed[0].fields
    assert "version" in diff.changed[0].fields
    assert diff.roots_changed is False
    assert diff.has_changes is True


def test_scan_diff_marks_root_selection_changes(tmp_path: Path) -> None:
    first = build_scan_snapshot([], roots=[tmp_path / "A"], created_at=1)
    second = build_scan_snapshot([], roots=[tmp_path / "B"], created_at=2)

    diff = compare_scan_snapshots(first, second)

    assert diff.roots_changed is True
    assert diff.has_changes is True


def test_snapshot_path_migration_prevents_false_remove_add(tmp_path: Path) -> None:
    old = tmp_path / "old.ffpfsc"
    new = tmp_path / "new.ffpfsc"
    previous = build_scan_snapshot(
        [_row(old)],
        roots=[tmp_path],
        file_states={old: FileState(100, 10)},
        created_at=1,
    )
    migrated = migrate_snapshot_paths(previous, [(old, new)])
    current = build_scan_snapshot(
        [_row(new)],
        roots=[tmp_path],
        file_states={new: FileState(100, 10)},
        created_at=2,
    )

    diff = compare_scan_snapshots(migrated, current)

    assert diff.added == ()
    assert diff.removed == ()
    assert diff.changed == ()


def test_malformed_snapshot_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text("{not json", encoding="utf-8")

    assert load_scan_snapshot(path) is None
