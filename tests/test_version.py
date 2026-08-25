from __future__ import annotations

from pathlib import Path
import tomllib

import ps5_ffpfsc_renamer


def test_runtime_version_matches_project_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert ps5_ffpfsc_renamer.__version__ == project["project"]["version"]
