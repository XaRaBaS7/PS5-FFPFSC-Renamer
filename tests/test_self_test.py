from __future__ import annotations

from ps5_ffpfsc_renamer.self_test import run_rename_safety_self_test


def test_rename_safety_self_test_passes_end_to_end() -> None:
    report = run_rename_safety_self_test()

    assert report.passed, report.as_text()
    assert report.failed_count == 0
    assert report.passed_count == 5
    assert "File-only rename and Undo" in report.as_text()
    assert "Batch rollback after late collision" in report.as_text()
