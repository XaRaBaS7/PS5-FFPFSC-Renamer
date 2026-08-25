from pathlib import Path

from ps5_ffpfsc_renamer.scanner import scan_ffpfsc


def test_recursive_scan(tmp_path: Path) -> None:
    (tmp_path / "a.ffpfsc").write_bytes(b"a")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.FFPFSC").write_bytes(b"b")
    (nested / "ignore.exfat").write_bytes(b"x")

    result = scan_ffpfsc(tmp_path, recursive=True)
    assert {path.name for path in result} == {"a.ffpfsc", "b.FFPFSC"}
