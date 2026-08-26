from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ps5_ffpfsc_renamer.scan_profile import ScanProfile
from ps5_ffpfsc_renamer.scan_report import (
    SCAN_REPORT_FORMAT,
    SCAN_REPORT_VERSION,
    export_scan_report_csv,
    export_scan_report_json,
    scan_profile_metrics,
)


def _profile() -> ScanProfile:
    return ScanProfile(
        total_files=100,
        selected_roots=3,
        effective_roots=2,
        unavailable_roots=1,
        cache_hits=80,
        failure_cache_hits=5,
        mkpfs_reads=20,
        workers=2,
        root_probe_seconds=0.1,
        discovery_seconds=0.2,
        cache_seconds=0.3,
        mkpfs_seconds=4.0,
        total_seconds=5.0,
    )


def test_scan_profile_metrics_are_aggregate_only() -> None:
    metrics = scan_profile_metrics(_profile())

    assert metrics["total_files"] == 100
    assert metrics["cache_hit_ratio"] == pytest.approx(0.8)
    assert metrics["files_per_second"] == pytest.approx(20.0)
    assert not any("path" in key or "file_name" in key for key in metrics)


def test_export_scan_report_json(tmp_path: Path) -> None:
    destination = tmp_path / "scan.json"
    export_scan_report_json(
        _profile(),
        destination,
        generated_at="2026-08-26T12:00:00+00:00",
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["report_format"] == SCAN_REPORT_FORMAT
    assert payload["report_version"] == SCAN_REPORT_VERSION
    assert payload["generated_at"] == "2026-08-26T12:00:00+00:00"
    assert payload["metrics"]["mkpfs_reads"] == 20
    assert payload["metrics"]["unavailable_roots"] == 1


def test_export_scan_report_csv(tmp_path: Path) -> None:
    destination = tmp_path / "scan.csv"
    export_scan_report_csv(
        _profile(),
        destination,
        generated_at="2026-08-26T12:00:00+00:00",
    )

    with destination.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row["report_format"] == SCAN_REPORT_FORMAT
    assert row["report_version"] == str(SCAN_REPORT_VERSION)
    assert row["total_files"] == "100"
    assert float(row["cache_hit_ratio"]) == pytest.approx(0.8)
    assert float(row["files_per_second"]) == pytest.approx(20.0)
