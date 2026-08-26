from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ExportRow:
    path: str
    filename: str
    title_id: str
    title: str
    version: str
    size_bytes: int | None
    proposed_output: str
    status: str
    duplicate_title_id: bool
    change_state: str = ""


EXPORT_FIELDS = (
    "path",
    "filename",
    "title_id",
    "title",
    "version",
    "size_bytes",
    "proposed_output",
    "status",
    "duplicate_title_id",
    "change_state",
)


def export_csv(rows: Iterable[ExportRow], destination: Path) -> Path:
    """Export a library snapshot as Excel-friendly UTF-8 CSV."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return destination


def export_json(rows: Iterable[ExportRow], destination: Path) -> Path:
    """Export a stable machine-readable library snapshot."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(row) for row in rows]
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination
