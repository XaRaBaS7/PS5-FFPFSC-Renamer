from pathlib import Path

from ps5_ffpfsc_renamer.root_health import probe_root, probe_roots, root_key


def test_probe_root_reports_online_directory(tmp_path: Path) -> None:
    status = probe_root(tmp_path)

    assert status.state == "ONLINE"
    assert status.available is True
    assert status.path == tmp_path.resolve()


def test_probe_root_reports_missing_path_without_removing_identity(tmp_path: Path) -> None:
    missing = tmp_path / "offline-drive" / "PS5"

    status = probe_root(missing)

    assert status.state == "OFFLINE"
    assert status.available is False
    assert status.path == missing.resolve(strict=False)


def test_probe_root_rejects_file_as_library_root(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-folder"
    file_path.write_text("x", encoding="utf-8")

    status = probe_root(file_path)

    assert status.state == "ERROR"
    assert "not a directory" in status.detail


def test_probe_roots_returns_casefolded_keys(tmp_path: Path) -> None:
    first = tmp_path / "A"
    second = tmp_path / "B"
    first.mkdir()
    second.mkdir()

    statuses = probe_roots([first, second])

    assert set(statuses) == {root_key(first), root_key(second)}
    assert all(status.available for status in statuses.values())


def test_root_key_does_not_resolve_or_probe_filesystem(monkeypatch) -> None:
    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("root_key must not resolve filesystem paths")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    key = root_key(Path("library") / ".." / "PS5")

    assert key.endswith("ps5")


def test_probe_root_falls_back_when_resolve_fails(monkeypatch, tmp_path: Path) -> None:
    def fail_resolve(*_args, **_kwargs):
        raise OSError("synthetic resolve failure")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    status = probe_root(tmp_path)

    assert status.state == "ONLINE"
    assert status.available is True
    assert status.path == tmp_path.absolute()
