from pathlib import Path

from ps5_ffpfsc_renamer import diagnostics
from ps5_ffpfsc_renamer.diagnostics import (
    classify_reader_error,
    diagnose_image,
    infer_metadata_from_path,
)
from ps5_ffpfsc_renamer.metadata import GameMetadata


def test_infer_ppsa_and_title_from_parent(tmp_path: Path) -> None:
    root = tmp_path / "library"
    folder = root / "DIRT5"
    folder.mkdir(parents=True)
    image = folder / "PPSA01552.ffpfsc"

    inferred = infer_metadata_from_path(image, library_root=root)

    assert inferred is not None
    assert inferred.metadata.title_id == "PPSA01552"
    assert inferred.metadata.title_name == "DIRT5"
    assert "folder" in inferred.source


def test_root_ppsa_does_not_invent_title(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    image = root / "PPSA01317.ffpfsc"

    inferred = infer_metadata_from_path(image, library_root=root)

    assert inferred is not None
    assert inferred.metadata.title_id == "PPSA01317"
    assert inferred.metadata.title_name is None


def test_filename_can_supply_title_and_ppsa(tmp_path: Path) -> None:
    image = tmp_path / "Returnal - PPSA01285.ffpfsc"

    inferred = infer_metadata_from_path(image, library_root=tmp_path)

    assert inferred is not None
    assert inferred.metadata.title_id == "PPSA01285"
    assert inferred.metadata.title_name == "Returnal"


def test_no_ppsa_means_no_fallback(tmp_path: Path) -> None:
    assert infer_metadata_from_path(tmp_path / "Unknown Game.ffpfsc") is None


def test_classify_no_inner_exfat() -> None:
    code, message = classify_reader_error("--deep: no inner exFAT found; showing the image tree")
    assert code == "no-inner-exfat"
    assert "exFAT" in message


def test_classify_truncated_read() -> None:
    code, message = classify_reader_error("failed to inspect image: truncated read at offset 0")
    assert code == "truncated-read"
    assert "incomplete/corrupt" in message


def test_classify_memory_safety_limit() -> None:
    code, message = classify_reader_error(
        "MkPFS memory safety limit exceeded while reading game.ffpfsc"
    )
    assert code == "memory-safety-limit"
    assert "stopped" in message


def test_classify_disabled_heavy_fallback() -> None:
    code, message = classify_reader_error(
        "Low-memory metadata path unavailable; heavy MkPFS fallback is disabled for safety."
    )
    assert code == "unsupported-bounded-layout"
    assert "protect system memory" in message


def test_packaged_diagnostics_do_not_run_recursive_mkpfs(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "PPSA01285.ffpfsc"
    image.write_bytes(b"synthetic")
    helper = tmp_path / "mkpfs-helper.exe"
    helper.write_bytes(b"helper")

    monkeypatch.setattr(diagnostics, "get_mkpfs_executable", lambda: None)
    monkeypatch.setattr(diagnostics, "_bundled_mkpfs_helper", lambda: helper)
    monkeypatch.setattr(
        diagnostics,
        "read_metadata",
        lambda *_args, **_kwargs: GameMetadata(
            title_id="PPSA01285",
            title_name="Safe Diagnostic",
            content_version="01.000.000",
        ),
    )
    monkeypatch.setattr(
        diagnostics,
        "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("packaged diagnostics must not run full MkPFS inspect/tree")
        ),
    )

    report = diagnose_image(image, library_root=tmp_path)

    assert "Reader mode: BOUNDED / PACKAGED" in report
    assert "Safe metadata probe: OK" in report
    assert "Full recursive MkPFS diagnostics were not required or started." in report
