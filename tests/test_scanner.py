from pathlib import Path

from ps5_ffpfsc_renamer.scanner import collapse_nested_roots, scan_ffpfsc


def test_recursive_scan(tmp_path: Path) -> None:
    (tmp_path / "a.ffpfsc").write_bytes(b"a")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.FFPFSC").write_bytes(b"b")
    (nested / "ignore.exfat").write_bytes(b"x")

    result = scan_ffpfsc(tmp_path, recursive=True)
    assert {path.name for path in result} == {"a.ffpfsc", "b.FFPFSC"}


def test_non_recursive_scan_stays_at_selected_root(tmp_path: Path) -> None:
    (tmp_path / "top.ffpfsc").write_bytes(b"top")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.ffpfsc").write_bytes(b"nested")

    result = scan_ffpfsc(tmp_path, recursive=False)

    assert [path.name for path in result] == ["top.ffpfsc"]


def test_recursive_scan_handles_large_synthetic_library(tmp_path: Path) -> None:
    expected: list[Path] = []
    for group in range(32):
        directory = tmp_path / f"group-{group:02d}"
        directory.mkdir()
        for index in range(32):
            suffix = ".FFPFSC" if index % 7 == 0 else ".ffpfsc"
            image = directory / f"game-{group:02d}-{index:02d}{suffix}"
            image.write_bytes(b"")
            expected.append(image)
        for index in range(4):
            (directory / f"ignore-{index}.exfat").write_bytes(b"")

    result = scan_ffpfsc(tmp_path, recursive=True)
    expected_sorted = sorted(expected, key=lambda path: str(path).casefold())

    assert len(result) == 1024
    assert result == expected_sorted
    assert len({str(path).casefold() for path in result}) == 1024


def test_collapse_nested_roots_keeps_only_parent_for_recursive_scan(tmp_path: Path) -> None:
    parent = tmp_path / "library"
    child = parent / "games"
    sibling = tmp_path / "other"
    child.mkdir(parents=True)
    sibling.mkdir()

    result = collapse_nested_roots([child, parent, sibling, child])

    assert result == [parent.resolve(), sibling.resolve()]


def test_collapse_nested_roots_does_not_collapse_similar_prefix_names(tmp_path: Path) -> None:
    first = tmp_path / "PS5"
    second = tmp_path / "PS5-backup"
    first.mkdir()
    second.mkdir()

    result = collapse_nested_roots([first, second])

    assert result == [first.resolve(), second.resolve()]
