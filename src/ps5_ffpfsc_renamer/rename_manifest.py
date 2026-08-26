from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .rename_plan import RenamePlanItem


@dataclass(frozen=True, slots=True)
class RenameManifestRow:
    source: str
    destination: str
    title_id: str
    title: str
    version: str
    status: str
    reason: str
    renames_directory: bool
    source_directory: str
    target_directory: str


FIELDS = (
    "source",
    "destination",
    "title_id",
    "title",
    "version",
    "status",
    "reason",
    "renames_directory",
    "source_directory",
    "target_directory",
)


def build_manifest_rows(items: Iterable[RenamePlanItem]) -> list[RenameManifestRow]:
    rows: list[RenameManifestRow] = []
    for item in items:
        metadata = item.metadata
        rows.append(
            RenameManifestRow(
                source=str(item.source),
                destination=str(item.destination),
                title_id=metadata.title_id,
                title=metadata.title_name or "",
                version=metadata.content_version or metadata.master_version or "",
                status=item.status.value.upper(),
                reason=item.reason,
                renames_directory=item.renames_directory,
                source_directory=str(item.source_directory or ""),
                target_directory=str(item.target_directory or ""),
            )
        )
    return rows


def export_manifest_csv(rows: Iterable[RenameManifestRow], destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return destination


def export_manifest_json(rows: Iterable[RenameManifestRow], destination: Path) -> Path:
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
