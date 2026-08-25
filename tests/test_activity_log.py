from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.activity_log import ActivityLog


def test_activity_log_writes_and_tails(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "activity.log", max_bytes=256 * 1024)
    first = log.write("info", "Scan started")
    second = log.write("mkpfs", "Processed game.ffpfsc\nextra detail")

    lines = log.tail(10)
    assert lines[-2:] == [first, second]
    assert "[INFO] Scan started" in first
    assert "[MKPFS] Processed game.ffpfsc | extra detail" in second


def test_activity_log_clear(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "activity.log")
    log.write("WARN", "Something happened")
    assert log.tail()
    log.clear()
    assert log.tail() == []


def test_activity_log_rotates(tmp_path: Path) -> None:
    path = tmp_path / "activity.log"
    log = ActivityLog(path, max_bytes=256 * 1024)
    path.write_text("x" * (256 * 1024 + 1), encoding="utf-8")
    log.write("INFO", "after rotation")

    assert path.exists()
    assert "after rotation" in path.read_text(encoding="utf-8")
    assert path.with_suffix(".log.1").exists()
