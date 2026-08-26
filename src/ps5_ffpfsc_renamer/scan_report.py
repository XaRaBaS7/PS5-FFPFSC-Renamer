from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .scan_profile import ScanProfile

SCAN_REPORT_FORMAT = "PS5-FFPFSC-Renamer-scan-performance"
SCAN_REPORT_VERSION = 1


def _generated_at(value: str | None = None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan_profile_metrics(profile: ScanProfile) -> dict[str, int | float]:
    """Return aggregate scan metrics without library paths or file metadata."""
    metrics = asdict(profile)
    metrics["cache_hit_ratio"] = profile.cache_hit_ratio
    metrics["files_per_second"] = profile.files_per_second
    return metrics


def scan_report_payload(
    profile: ScanProfile,
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Return the portable JSON report payload for one completed scan."""
    return {
        "report_format": SCAN_REPORT_FORMAT,
        "report_version": SCAN_REPORT_VERSION,
        "generated_at": _generated_at(generated_at),
        "metrics": scan_profile_metrics(profile),
    }


def export_scan_report_json(
    profile: ScanProfile,
    destination: Path,
    *,
    generated_at: str | None = None,
) -> Path:
    """Export the last scan profile as aggregate JSON metrics."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            scan_report_payload(profile, generated_at=generated_at),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def export_scan_report_csv(
    profile: ScanProfile,
    destination: Path,
    *,
    generated_at: str | None = None,
) -> Path:
    """Export the last scan profile as one CSV row of aggregate metrics."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {
        "report_format": SCAN_REPORT_FORMAT,
        "report_version": SCAN_REPORT_VERSION,
        "generated_at": _generated_at(generated_at),
        **scan_profile_metrics(profile),
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    temporary.replace(destination)
    return destination
