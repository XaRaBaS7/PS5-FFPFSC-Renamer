from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_package_keeps_required_docs_and_mkpfs_source_without_redundant_root_assets() -> None:
    for workflow_name in ("build-windows.yml", "release.yml"):
        text = (ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
        assert 'Copy-Item ".\\README.md" "$app\\README.md"' in text
        assert 'Copy-Item ".\\CHANGELOG.md" "$app\\CHANGELOG.md"' in text
        assert 'Copy-Item ".\\LICENSE" "$app\\LICENSE.md"' not in text
        assert 'Copy-Item ".\\LICENSE" "$app\\LICENSE"' in text
        assert 'Copy-Item ".\\THIRD_PARTY_NOTICES.md" "$app\\THIRD_PARTY_NOTICES.md"' in text
        assert 'source\\third-party' in text
        assert 'mkpfs==0.0.9' in text
        assert 'Copy-Item ".\\tools\\mkpfs_helper.py" "$app\\source\\third-party\\mkpfs_helper.py"' in text
        assert 'Copy-Item ".\\assets\\app-icon.png"' not in text
        assert 'Copy-Item ".\\assets\\brand\\*"' not in text
        assert 'Unexpected redundant app-icon.png in package root' in text
        assert 'Unexpected redundant assets directory in package root' in text
        assert 'Bundled brand assets are missing' in text
        assert '$package = ".\\dist\\PS5-FFPFSC-Renamer-v$version-Windows-x64"' in text
        assert "Move-Item $app $package" in text
        assert "Compress-Archive -Path $package" in text


def test_feedback_button_is_enabled_for_send_only_after_receiver_health_check() -> None:
    text = (ROOT / "src" / "ps5_ffpfsc_renamer" / "ui" / "feedback_mixin.py").read_text(encoding="utf-8")
    assert "feedback_endpoint_health" in text
    assert 'text="Send report" if health.available else "Save report locally"' in text
    assert 'text="Checking..."' in text
    assert 'text="Check connection"' in text
    assert 'if not endpoint_state["ready"]:' in text
    assert "save_local()" in text


def test_production_feedback_endpoint_is_https_and_matches_deploy_target() -> None:
    text = (ROOT / "src" / "ps5_ffpfsc_renamer" / "feedback_transport.py").read_text(encoding="utf-8")
    endpoint = "https://www.youstoreinformatica.com/ffpfsc/ps5-ffpfsc-feedback.php"
    assert f'DEFAULT_FEEDBACK_ENDPOINT = "{endpoint}"' in text
    deploy = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    assert endpoint in deploy


def test_php_receiver_exposes_expected_health_identity() -> None:
    text = (ROOT / "deploy" / "ffpfsc" / "ps5-ffpfsc-feedback.php").read_text(encoding="utf-8")
    assert "const FEEDBACK_SERVICE = 'ps5-ffpfsc-feedback';" in text
    assert "'service' => FEEDBACK_SERVICE" in text
    assert "$method === 'GET'" in text
    assert "respond(202" in text


def test_feedback_admin_is_private_and_does_not_embed_credentials() -> None:
    panel = (ROOT / "deploy" / "ffpfsc" / "admin" / "index.php").read_text(encoding="utf-8")
    config = (ROOT / "deploy" / "ffpfsc" / "admin-config.example.php").read_text(encoding="utf-8")
    deny = (ROOT / "deploy" / "ffpfsc" / "feedback-data" / ".htaccess").read_text(encoding="utf-8")
    assert "password_verify" in panel
    assert "session_regenerate_id" in panel
    assert "hash_equals" in panel
    assert "Prepare GitHub issue" in panel
    assert "REPLACE_WITH_PASSWORD_HASH" in config
    assert "Require all denied" in deny
