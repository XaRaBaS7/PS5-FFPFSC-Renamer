from __future__ import annotations

import csv
import json
from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.rename_manifest import (
    build_manifest_rows,
    export_manifest_csv,
    export_manifest_json,
)
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, RenamePlanItem


def _item(tmp_path: Path, status: PlanStatus = PlanStatus.READY) -> RenamePlanItem:
    source = tmp_path / "old.ffpfsc"
    destination = tmp_path / "PPSA01285 - Returnal.ffpfsc"
    return RenamePlanItem(
        source=source,
        destination=destination,
        metadata=GameMetadata(
            title_id="PPSA01285",
            title_name="Returnal",
            content_version="01.000.000",
        ),
        status=status,
        reason="target file already exists" if status is PlanStatus.COLLISION else "",
    )


def test_manifest_rows_capture_plan_without_touching_files(tmp_path: Path) -> None:
    item = _item(tmp_path)
    rows = build_manifest_rows([item])

    assert len(rows) == 1
    row = rows[0]
    assert row.source == str(item.source)
    assert row.destination == str(item.destination)
    assert row.title_id == "PPSA01285"
    assert row.title == "Returnal"
    assert row.version == "01.000.000"
    assert row.status == "READY"
    assert not item.source.exists()
    assert not item.destination.exists()


def test_manifest_keeps_block_reason(tmp_path: Path) -> None:
    rows = build_manifest_rows([_item(tmp_path, PlanStatus.COLLISION)])

    assert rows[0].status == "COLLISION"
    assert rows[0].reason == "target file already exists"


def test_manifest_csv_and_json_exports(tmp_path: Path) -> None:
    rows = build_manifest_rows([_item(tmp_path)])
    csv_path = tmp_path / "plan.csv"
    json_path = tmp_path / "plan.json"

    export_manifest_csv(rows, csv_path)
    export_manifest_json(rows, json_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert csv_rows[0]["title_id"] == "PPSA01285"
    assert csv_rows[0]["status"] == "READY"
    assert payload[0]["destination"].endswith("PPSA01285 - Returnal.ffpfsc")
