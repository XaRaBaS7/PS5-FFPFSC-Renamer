from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.feedback_report import (
    build_exception_payload,
    collect_diagnostics,
    create_feedback_report,
    redact_text,
)
from ps5_ffpfsc_renamer.root_health import RootStatus


def test_feedback_redaction_removes_library_root_and_user_profile(monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", r"C:\Users\ExampleUser")
    monkeypatch.setenv("USERNAME", "ExampleUser")
    root_text = r"D:\PS5\Library"
    root = Path(root_text)
    text = (
        rf"Failure reading {root_text}\PPSA00001.ffpfsc from "
        r"C:\Users\ExampleUser\AppData\Local"
    )

    clean = redact_text(text, roots=[root])

    assert root_text not in clean
    assert "ExampleUser" not in clean
    assert "<ROOT_1>" in clean
    assert "<HOME>" in clean or "<USER>" in clean


def test_feedback_report_sanitizes_description_activity_and_exception(monkeypatch) -> None:
    monkeypatch.setenv("USERNAME", "PrivateUser")
    root_text = r"Z:\Archive"
    root = Path(root_text)
    report = create_feedback_report(
        category="Bug report",
        summary=f"Crash in {root_text}",
        description=rf"PrivateUser saw {root_text}\game.ffpfsc fail",
        diagnostics={"note": rf"{root_text}\game.ffpfsc"},
        roots=[root],
        exception={"type": "RuntimeError", "message": f"{root_text} failed"},
        activity_lines=[rf"Reading {root_text}\game.ffpfsc as PrivateUser"],
        report_id="fixed-id",
        created_at="2026-08-26T20:00:00+00:00",
    )
    payload = report.payload()
    serialized = str(payload)

    assert "PrivateUser" not in serialized
    assert root_text not in serialized
    assert payload["report_id"] == "fixed-id"
    assert payload["exception"]["type"] == "RuntimeError"


def test_collect_diagnostics_contains_counts_not_root_paths() -> None:
    roots = [
        RootStatus(Path(r"D:\Games"), "ONLINE", "available"),
        RootStatus(Path(r"Z:\NAS"), "OFFLINE", "unavailable"),
    ]
    diagnostics = collect_diagnostics(
        root_statuses=roots,
        record_statuses=["READY", "READY", "OFFLINE", "ERROR"],
        duplicate_group_count=2,
        scan_total=4,
        cache_hits=3,
        mkpfs_reads=1,
        scan_elapsed=1.25,
        worker_count=2,
        scan_active=False,
        live_watch=False,
        watch_interval_seconds=30,
        result_filter="ALL",
    )

    assert diagnostics["root_states"] == {"OFFLINE": 1, "ONLINE": 1}
    assert diagnostics["record_states"] == {"ERROR": 1, "OFFLINE": 1, "READY": 2}
    assert diagnostics["last_scan"]["files"] == 4
    assert r"D:\Games" not in str(diagnostics)
    assert r"Z:\NAS" not in str(diagnostics)


def test_exception_payload_redacts_traceback_paths(monkeypatch) -> None:
    monkeypatch.setenv("USERNAME", "SecretUser")
    root_text = r"D:\PS5"
    root = Path(root_text)
    try:
        raise RuntimeError(rf"failed at {root_text}\game.ffpfsc for SecretUser")
    except RuntimeError as exc:
        payload = build_exception_payload(type(exc), exc, exc.__traceback__, roots=[root])

    assert payload["type"] == "RuntimeError"
    assert root_text not in payload["message"]
    assert "SecretUser" not in payload["traceback"]
