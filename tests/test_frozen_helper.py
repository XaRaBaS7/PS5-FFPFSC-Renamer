from pathlib import Path

from ps5_ffpfsc_renamer import ffpfsc_reader


def test_frozen_build_prefers_sibling_mkpfs_helper(tmp_path: Path, monkeypatch) -> None:
    app = tmp_path / "PS5-FFPFSC-Renamer.exe"
    helper = tmp_path / "mkpfs-helper.exe"
    app.write_bytes(b"app")
    helper.write_bytes(b"helper")

    monkeypatch.setattr(ffpfsc_reader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ffpfsc_reader.sys, "executable", str(app))

    assert ffpfsc_reader.mkpfs_available()
    assert ffpfsc_reader._mkpfs_command() == [str(helper)]


def test_frozen_build_reports_missing_helper(tmp_path: Path, monkeypatch) -> None:
    app = tmp_path / "PS5-FFPFSC-Renamer.exe"
    app.write_bytes(b"app")

    monkeypatch.setattr(ffpfsc_reader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ffpfsc_reader.sys, "executable", str(app))
    monkeypatch.setattr(ffpfsc_reader.shutil, "which", lambda _name: None)

    assert not ffpfsc_reader.mkpfs_available()
    try:
        ffpfsc_reader._mkpfs_command()
    except ffpfsc_reader.MetadataReadError as exc:
        assert "helper is missing" in str(exc)
    else:
        raise AssertionError("expected MetadataReadError")
