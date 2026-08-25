from __future__ import annotations

import csv
import json
from pathlib import Path

from ps5_ffpfsc_renamer.library_export import ExportRow, export_csv, export_json


def _rows() -> list[ExportRow]:
    return [
        ExportRow(
            path=r"D:\PS5\Returnal\PPSA01285.ffpfsc",
            filename="PPSA01285.ffpfsc",
            title_id="PPSA01285",
            title="Returnal",
            version="1.0",
            size_bytes=123456789,
            proposed_output="PPSA01285 - Returnal.ffpfsc",
            status="READY",
            duplicate_title_id=False,
        )
    ]


def test_csv_export_is_excel_friendly_utf8(tmp_path: Path) -> None:
    destination = tmp_path / "library.csv"
    export_csv(_rows(), destination)

    raw = destination.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with destination.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["title_id"] == "PPSA01285"
    assert rows[0]["title"] == "Returnal"


def test_json_export_has_stable_fields(tmp_path: Path) -> None:
    destination = tmp_path / "library.json"
    export_json(_rows(), destination)

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload[0]["filename"] == "PPSA01285.ffpfsc"
    assert payload[0]["duplicate_title_id"] is False
    assert payload[0]["size_bytes"] == 123456789
