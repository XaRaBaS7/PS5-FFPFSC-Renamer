from __future__ import annotations

from pathlib import Path
import re
import tomllib

import ps5_ffpfsc_renamer


def _project_version() -> str:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return project["project"]["version"]


def test_v050b_metadata_is_synchronized_without_relabeling_v050_stable() -> None:
    version = _project_version()
    assert version == "0.5.0b"
    assert ps5_ffpfsc_renamer.__version__ == version

    readme = Path("README.md").read_text(encoding="utf-8")
    preview = Path("docs/screenshots/app-preview.svg").read_text(encoding="utf-8")

    assert "**Current stable release:** `v0.5.0`" in readme
    assert f">v{version}<" in preview


def test_alpha_metadata_contains_no_old_development_marker() -> None:
    files = (
        "README.md",
        "CHANGELOG.md",
        "RELEASE_NOTES.md",
        "docs/screenshots/app-preview.svg",
    )
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert "0.5.0.dev1" not in text
    assert not re.search(r"v0\.5(?:\.0)?-dev", text, flags=re.IGNORECASE)
