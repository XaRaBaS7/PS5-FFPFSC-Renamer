from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.library_watch import (
    LibrarySnapshot,
    changed_paths,
    diff_snapshots,
    snapshot_library,
)


def test_snapshot_library_detects_ffpfsc_and_ignores_other_files(tmp_path: Path):
    root = tmp_path / "games"
    root.mkdir()
    first = root / "A.ffpfsc"
    first.write_bytes(b"a")
    (root / "ignore.txt").write_text("x", encoding="utf-8")

    snap = snapshot_library([root], recursive=True)

    assert snap.file_count == 1
    assert snap.files[0][0].endswith("A.ffpfsc")
    assert snap.unavailable_roots == ()


def test_snapshot_library_reports_unavailable_root(tmp_path: Path):
    missing = tmp_path / "missing"
    snap = snapshot_library([missing])
    assert snap.file_count == 0
    assert snap.unavailable_roots == (str(missing),)


def test_diff_snapshots_classifies_added_removed_modified():
    before = LibrarySnapshot(
        (
            ("A.ffpfsc", 100, 1),
            ("B.ffpfsc", 200, 1),
            ("C.ffpfsc", 300, 1),
        )
    )
    after = LibrarySnapshot(
        (
            ("B.ffpfsc", 201, 2),
            ("C.ffpfsc", 300, 1),
            ("D.ffpfsc", 400, 1),
        )
    )

    changes = diff_snapshots(before, after)

    assert changes.added == ("D.ffpfsc",)
    assert changes.removed == ("A.ffpfsc",)
    assert changes.modified == ("B.ffpfsc",)
    assert changes.total == 3
    assert changed_paths(before, after) == ("A.ffpfsc", "B.ffpfsc", "D.ffpfsc")
