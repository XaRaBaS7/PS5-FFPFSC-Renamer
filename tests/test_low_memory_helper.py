from __future__ import annotations

import io
import json
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

from mkpfs import consts
from ps5_ffpfsc_renamer import ffpfsc_reader
from tools import mkpfs_helper


def _build_synthetic_ffpfsc(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = tmp_path / "game"
    sce_sys = source / "sce_sys"
    sce_sys.mkdir(parents=True)
    param: dict[str, object] = {
        "titleId": "PPSA01285",
        "contentVersion": "01.000.000",
        "masterVersion": "01.00",
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Low Memory Test"},
        },
    }
    (sce_sys / "param.json").write_text(json.dumps(param), encoding="utf-8")

    # Unrelated content makes sure the metadata path does not rely on the game
    # containing only sce_sys/param.json.
    for index in range(24):
        folder = source / "content" / f"dir-{index:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"payload-{index:02d}.bin").write_bytes((f"payload-{index}".encode()) * 128)

    image = tmp_path / "synthetic.ffpfsc"
    completed = subprocess.run(
        [
            "mkpfs",
            "pack",
            "folder",
            str(source),
            str(image),
            "--no-adjust-output-file-extension",
            "--skip-verification",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return image, param


def test_low_memory_helper_reads_only_param_json(tmp_path: Path) -> None:
    image, expected = _build_synthetic_ffpfsc(tmp_path)
    output = tmp_path / "param.json"

    mkpfs_helper.extract_param_json_low_memory(image, output)

    assert json.loads(output.read_text(encoding="utf-8")) == expected


def test_low_memory_view_does_not_materialize_pfsc_offset_list(tmp_path: Path) -> None:
    image, _expected = _build_synthetic_ffpfsc(tmp_path)
    view, handle, _inner_name = mkpfs_helper._open_low_memory_inner_view(image)
    try:
        assert view._block_count > 0
        assert not hasattr(view, "_offsets")
        assert len(view._offset_page_cache) <= mkpfs_helper._OFFSET_CACHE_PAGES
    finally:
        handle.close()


def test_low_memory_view_pages_large_offset_table_without_materializing_it(monkeypatch) -> None:
    block_count = 10_000_000
    block_offsets_offset = consts.PFSC_BLOCK_OFFSETS_OFFSET
    data_offset = 100_000_000
    stored_size = 900_000_000
    header = SimpleNamespace(block_size=0x10000)
    inode = SimpleNamespace(
        db=[1],
        is_compressed=True,
        logical_size=block_count * consts.PFSC_LOGICAL_BLOCK_SIZE,
        stored_size=stored_size,
    )
    base = header.block_size
    reads: list[int] = []

    def _fake_raw(self, offset: int, size: int) -> bytes:
        reads.append(size)
        if size == consts.PFSC_HEADER_SIZE:
            return b"\0" * size
        assert 0 < size <= mkpfs_helper._OFFSET_PAGE_BYTES
        page_start = offset - base - block_offsets_offset
        page = bytearray(size)
        first_entry = 0
        final_entry = block_count * 8
        if page_start <= first_entry < page_start + size:
            struct.pack_into("<Q", page, first_entry - page_start, data_offset)
        if page_start <= final_entry < page_start + size:
            struct.pack_into("<Q", page, final_entry - page_start, stored_size)
        return bytes(page)

    monkeypatch.setattr(
        mkpfs_helper.mkpfs_pfs,
        "_parse_pfsc_header",
        lambda _head: (
            consts.PFSC_LOGICAL_BLOCK_SIZE,
            block_count,
            block_offsets_offset,
            data_offset,
            inode.logical_size,
        ),
    )
    monkeypatch.setattr(mkpfs_helper._LowMemoryLogicalFileView, "_raw", _fake_raw)

    view = mkpfs_helper._LowMemoryLogicalFileView(io.BytesIO(), header, inode)

    assert view._block_count == block_count
    assert not hasattr(view, "_offsets")
    assert reads[0] == consts.PFSC_HEADER_SIZE
    assert max(reads[1:]) <= mkpfs_helper._OFFSET_PAGE_BYTES
    assert sum(reads[1:]) <= mkpfs_helper._OFFSET_PAGE_BYTES * 2
    assert len(view._offset_page_cache) <= mkpfs_helper._OFFSET_CACHE_PAGES


def test_frozen_reader_uses_bundled_param_command(tmp_path: Path, monkeypatch) -> None:
    app = tmp_path / "PS5-FFPFSC-Renamer.exe"
    helper = tmp_path / "mkpfs-helper.exe"
    image = tmp_path / "game.ffpfsc"
    app.write_bytes(b"app")
    helper.write_bytes(b"helper")
    image.write_bytes(b"image")

    monkeypatch.setattr(ffpfsc_reader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ffpfsc_reader.sys, "executable", str(app))
    captured: list[str] = []

    class _Process:
        returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def poll(self) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    def _popen(command: list[str], **_kwargs: object) -> _Process:
        captured[:] = command
        assert command[0] == str(helper)
        assert command[1] == "read-param-json"
        Path(command[3]).write_text(
            json.dumps(
                {
                    "titleId": "PPSA01285",
                    "localizedParameters": {
                        "defaultLanguage": "en-US",
                        "en-US": {"titleName": "Bundled Helper Test"},
                    },
                }
            ),
            encoding="utf-8",
        )
        return _Process()

    monkeypatch.setattr(ffpfsc_reader.subprocess, "Popen", _popen)
    metadata = ffpfsc_reader.read_metadata(image, use_cache=False)

    assert captured[1] == "read-param-json"
    assert metadata.title_id == "PPSA01285"
    assert metadata.title_name == "Bundled Helper Test"
