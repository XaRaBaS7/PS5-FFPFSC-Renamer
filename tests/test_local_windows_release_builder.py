from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_windows_release.ps1"


def test_local_windows_release_builder_keeps_v050_and_runs_required_checks() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '[string]$ExpectedVersion = "0.5.0"' in text
    assert '"-m" "compileall" "-q" "src" "tools"' in text
    assert '"-m" "pytest" "-q"' in text
    assert '"mkpfs==0.0.9"' in text
    assert '"read-param-json"' in text
    assert '"_internal\\assets\\brand"' in text
    assert '"source\\third-party\\mkpfs_helper.py"' in text
    assert "Unexpected redundant assets directory in package root" in text
    assert "Unexpected redundant app-icon.png in package root" in text
    assert "Smoke-test frozen desktop startup" in text


def test_local_windows_release_builder_does_not_publish_or_move_tags() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()

    assert "gh release" not in text
    assert "git tag" not in text
    assert "git push" not in text
    assert "release create" not in text
    assert "release upload" not in text


def test_local_windows_release_builder_creates_versioned_top_level_zip() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '$packageName = "PS5-FFPFSC-Renamer-v$version-Windows-x64"' in text
    assert "Compress-Archive -Path $packageDir" in text
    assert "$prefix = $packageName + \"/\"" in text
    assert "entries outside the expected top-level" in text
