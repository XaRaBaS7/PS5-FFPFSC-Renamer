from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ps5_ffpfsc_renamer.ffpfsc_reader import read_metadata


def test_mkpfs_roundtrip_metadata(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-game"
    sce_sys = source / "sce_sys"
    sce_sys.mkdir(parents=True)

    param = {
        "titleId": "PPSA01285",
        "contentVersion": "01.000.000",
        "masterVersion": "01.00",
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Synthetic Test Game"},
        },
    }
    (sce_sys / "param.json").write_text(json.dumps(param), encoding="utf-8")
    (source / "dummy.bin").write_bytes(b"PS5-FFPFSC-Renamer integration test")

    image = tmp_path / "synthetic.ffpfsc"
    completed = subprocess.run(
        [
            "mkpfs",
            "pack",
            "folder",
            str(source),
            str(image),
            "--no-adjust-output-file-extension",
            "--skip-verification",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert image.is_file()

    # Force a real MkPFS read here so this end-to-end test never passes only
    # because a previous cache entry exists.
    metadata = read_metadata(image, use_cache=False)
    assert metadata.title_id == "PPSA01285"
    assert metadata.title_name == "Synthetic Test Game"
    assert metadata.content_version == "01.000.000"
