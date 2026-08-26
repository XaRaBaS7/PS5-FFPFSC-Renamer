from __future__ import annotations

from pathlib import Path
import re
import tomllib

import ps5_ffpfsc_renamer


def _project_version() -> str:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return project["project"]["version"]


def test_v050_release_metadata_is_synchronized() -> None:
    version = _project_version()
    assert version == "0.5.0"
    assert ps5_ffpfsc_renamer.__version__ == version

    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    notes = Path("RELEASE_NOTES.md").read_text(encoding="utf-8")
    preview = Path("docs/screenshots/app-preview.svg").read_text(encoding="utf-8")

    assert f"**Current stable release:** `v{version}`" in readme
    assert f"## [{version}] - 2026-08-27" in changelog
    assert notes.startswith(f"# PS5 FFPFSC Renamer v{version}")
    assert f">v{version}<" in preview


def test_stable_metadata_contains_no_v050_development_marker() -> None:
    files = (
        "README.md",
        "CHANGELOG.md",
        "RELEASE_NOTES.md",
        "docs/screenshots/app-preview.svg",
    )
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert "0.5.0.dev1" not in text
    assert not re.search(r"v0\.5(?:\.0)?-dev", text, flags=re.IGNORECASE)
