from pathlib import Path

from ps5_ffpfsc_renamer.diagnostics import (
    classify_reader_error,
    infer_metadata_from_path,
)


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
