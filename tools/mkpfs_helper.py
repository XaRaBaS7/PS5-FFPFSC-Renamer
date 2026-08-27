from __future__ import annotations

import shutil
import struct
import sys
import tempfile
from collections.abc import Iterator
from multiprocessing import freeze_support
from pathlib import Path
from typing import BinaryIO

from mkpfs import consts
from mkpfs import pfs as mkpfs_pfs
from mkpfs.__main__ import main as mkpfs_main
from mkpfs.exfat import ExfatEntry, ExfatError, ExfatReader
from zlib_ng import zlib_ng as zlib


_READ_PARAM_COMMAND = "read-param-json"
_MAX_EXFAT_CLUSTER_SIZE = 32 * 1024 * 1024
_OFFSET_PAGE_BYTES = 64 * 1024
_OFFSET_CACHE_PAGES = 8
_ENTRY_FILE = 0x85
_ENTRY_STREAM_EXTENSION = 0xC0
_ENTRY_FILE_NAME = 0xC1
_ATTR_DIRECTORY = 0x10
_SECONDARY_FLAG_NO_FAT_CHAIN = 0x02


class LowMemoryMetadataError(RuntimeError):
    """Raised when the bounded-memory metadata path cannot read the target."""


class LowMemoryMetadataUnavailable(LowMemoryMetadataError):
    """Raised for legacy layouts that require the normal MkPFS extractor."""


class _LowMemoryLogicalFileView(mkpfs_pfs._LogicalFileView):
    """Seekable PFSC view with a bounded, paged block-offset cache.

    MkPFS 0.0.9's normal ``_LogicalFileView`` expands the complete PFSC offset
    table into a Python ``list[int]``. Large logical images can therefore spend
    memory proportional to total image size before exFAT parsing even starts.

    This view keeps only a few 64 KiB pages of offset entries. Page caching also
    avoids turning the memory fix into repeated tiny seeks between the PFSC
    offset table and compressed data on HDD/NAS-backed libraries.
    """

    def __init__(
        self,
        fh: BinaryIO,
        header: mkpfs_pfs.ParsedHeader,
        inode: mkpfs_pfs.ParsedInode,
        ekpfs: bytes | None = None,
        new_crypt: bool = False,
    ) -> None:
        self._fh = fh
        self._header = header
        self._ekpfs = ekpfs
        self._new_crypt = new_crypt
        self._base = inode.db[0] * header.block_size
        self._compressed = inode.is_compressed
        self._size = inode.logical_size
        self._stored_size = inode.stored_size
        self._pos = 0
        self._cache: dict[int, bytes] = {}
        self._order: list[int] = []
        self._block_count = 0
        self._block_offsets_offset = 0
        self._data_offset = 0
        self._offset_table_bytes = 0
        self._offset_page_cache: dict[int, bytes] = {}
        self._offset_page_order: list[int] = []

        if self._compressed:
            head = self._raw(self._base, consts.PFSC_HEADER_SIZE)
            (
                self._lbs,
                self._block_count,
                self._block_offsets_offset,
                self._data_offset,
                _logical_size,
            ) = mkpfs_pfs._parse_pfsc_header(head)
            if self._block_count <= 0:
                raise LowMemoryMetadataError("PFSC payload contains no logical blocks")
            self._offset_table_bytes = (self._block_count + 1) * 8

            first_offset = self._read_offset(0)
            final_offset = self._read_offset(self._block_count)
            if first_offset != self._data_offset:
                raise LowMemoryMetadataError("PFSC offset table does not start at data_offset")
            if final_offset < first_offset or final_offset > self._stored_size:
                raise LowMemoryMetadataError("PFSC offset table exceeds the stored payload")

    def _read_offset_page(self, page_index: int) -> bytes:
        cached = self._offset_page_cache.get(page_index)
        if cached is not None:
            return cached

        page_start = page_index * _OFFSET_PAGE_BYTES
        if page_start < 0 or page_start >= self._offset_table_bytes:
            raise LowMemoryMetadataError(f"PFSC offset page out of range: {page_index}")
        page_size = min(_OFFSET_PAGE_BYTES, self._offset_table_bytes - page_start)
        raw = self._raw(self._base + self._block_offsets_offset + page_start, page_size)
        if len(raw) != page_size:
            raise LowMemoryMetadataError("PFSC offset table is truncated")

        self._offset_page_cache[page_index] = raw
        self._offset_page_order.append(page_index)
        if len(self._offset_page_order) > _OFFSET_CACHE_PAGES:
            old_page = self._offset_page_order.pop(0)
            self._offset_page_cache.pop(old_page, None)
        return raw

    def _read_offset(self, index: int) -> int:
        if not 0 <= index <= self._block_count:
            raise LowMemoryMetadataError(f"PFSC block offset index out of range: {index}")
        byte_offset = index * 8
        page_index, page_offset = divmod(byte_offset, _OFFSET_PAGE_BYTES)
        page = self._read_offset_page(page_index)
        if page_offset + 8 > len(page):
            raise LowMemoryMetadataError("PFSC offset entry crosses a truncated page")
        return struct.unpack_from("<Q", page, page_offset)[0]

    def _decode_block(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        if not 0 <= index < self._block_count:
            raise LowMemoryMetadataError(f"PFSC block index out of range: {index}")

        start = self._read_offset(index)
        end = self._read_offset(index + 1)
        if start < self._data_offset or end < start or end > self._stored_size:
            raise LowMemoryMetadataError(f"Invalid PFSC stored range for block {index}")

        stored = self._raw(self._base + start, end - start)
        try:
            block = stored if len(stored) == self._lbs else zlib.decompress(stored)
        except zlib.error as exc:
            raise LowMemoryMetadataError(f"PFSC block {index} is not valid zlib data") from exc
        if len(block) > self._lbs:
            raise LowMemoryMetadataError(f"PFSC block {index} exceeds its logical block size")

        self._cache[index] = block
        self._order.append(index)
        if len(self._order) > self._CACHE_BLOCKS:
            self._cache.pop(self._order.pop(0), None)
        return block


def _open_low_memory_inner_view(image: Path) -> tuple[_LowMemoryLogicalFileView, BinaryIO, str]:
    inspection = mkpfs_pfs.inspect_pfs_image(image=image, verify_payloads=False)
    if inspection.errors:
        detail = "; ".join(str(error) for error in inspection.errors[:3])
        raise LowMemoryMetadataError(detail or "PFS inspection failed")
    if inspection.header is None:
        raise LowMemoryMetadataError("PFS image header is unavailable")
    if len(inspection.file_inodes) != 1:
        raise LowMemoryMetadataUnavailable("image is not a supported single-file wrapped PFS")

    rel_name, inode_num = next(iter(inspection.file_inodes.items()))
    inode = inspection.inodes[inode_num]
    if inode.db_sig or inode.ib_sig or inode.blocks <= 0 or inode.logical_size <= 0:
        raise LowMemoryMetadataUnavailable("wrapped payload uses a signed, scattered, or empty layout")

    fh = image.open("rb")
    try:
        view = _LowMemoryLogicalFileView(fh, inspection.header, inode)
    except Exception:
        fh.close()
        raise
    return view, fh, rel_name


def _iter_directory_level(
    reader: ExfatReader,
    first_cluster: int,
    no_fat_chain: bool,
    length: int,
    rel_dir: str,
) -> Iterator[ExfatEntry]:
    """Yield one exFAT directory level without recursively building a tree."""
    raw_entries = iter(reader._read_directory_entries(first_cluster, no_fat_chain, length))
    for entry in raw_entries:
        if entry[0] != _ENTRY_FILE:
            continue

        secondary_count = entry[1]
        secondaries: list[bytes] = []
        try:
            for _ in range(secondary_count):
                secondaries.append(next(raw_entries))
        except StopIteration:
            return
        if not secondaries or secondaries[0][0] != _ENTRY_STREAM_EXTENSION:
            continue

        file_attrs = struct.unpack_from("<H", entry, 0x04)[0]
        stream = secondaries[0]
        flags = stream[1]
        name_length = stream[3]
        data_length = struct.unpack_from("<Q", stream, 0x18)[0]
        child_cluster = struct.unpack_from("<I", stream, 0x14)[0]
        child_no_fat = bool(flags & _SECONDARY_FLAG_NO_FAT_CHAIN)

        name_units = bytearray()
        for secondary in secondaries[1:]:
            if secondary[0] == _ENTRY_FILE_NAME:
                name_units += secondary[2:32]
        name = name_units.decode("utf-16-le", errors="replace")[:name_length]
        rel_path = f"{rel_dir}/{name}" if rel_dir else name
        yield ExfatEntry(
            name=name,
            rel_path=rel_path,
            is_dir=bool(file_attrs & _ATTR_DIRECTORY),
            first_cluster=child_cluster,
            length=data_length,
            no_fat_chain=child_no_fat,
        )


def _find_unique_child(
    reader: ExfatReader,
    *,
    first_cluster: int,
    no_fat_chain: bool,
    length: int,
    rel_dir: str,
    name: str,
) -> ExfatEntry:
    target = name.casefold()
    matches = [
        entry
        for entry in _iter_directory_level(reader, first_cluster, no_fat_chain, length, rel_dir)
        if entry.name.casefold() == target
    ]
    if len(matches) != 1:
        raise LowMemoryMetadataError(
            f"Expected one '{name}' entry under '{rel_dir or '/'}', found {len(matches)}"
        )
    return matches[0]


def extract_param_json_low_memory(image: Path, output: Path) -> None:
    """Extract only ``sce_sys/param.json`` using bounded-memory random reads."""
    view, fh, _inner_name = _open_low_memory_inner_view(image)
    try:
        try:
            reader = ExfatReader(view)
        except ExfatError as exc:
            raise LowMemoryMetadataError(f"wrapped payload is not valid exFAT: {exc}") from exc

        cluster_size = reader.geometry.cluster_size
        if not 512 <= cluster_size <= _MAX_EXFAT_CLUSTER_SIZE:
            raise LowMemoryMetadataError(f"unsupported exFAT cluster size: {cluster_size} bytes")

        sce_sys = _find_unique_child(
            reader,
            first_cluster=reader.geometry.root_dir_cluster,
            no_fat_chain=False,
            length=0,
            rel_dir="",
            name="sce_sys",
        )
        if not sce_sys.is_dir:
            raise LowMemoryMetadataError("sce_sys is not a directory")

        param = _find_unique_child(
            reader,
            first_cluster=sce_sys.first_cluster,
            no_fat_chain=sce_sys.no_fat_chain,
            length=sce_sys.length,
            rel_dir=sce_sys.rel_path,
            name="param.json",
        )
        if param.is_dir:
            raise LowMemoryMetadataError("sce_sys/param.json is a directory")

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as destination:
            for chunk in reader.read_file(param, chunk_size=1024 * 1024):
                destination.write(chunk)
    finally:
        fh.close()


def _fallback_extract_param_json(image: Path, output: Path) -> int:
    """Preserve compatibility for legacy direct-PFS layouts."""
    with tempfile.TemporaryDirectory(prefix="mkpfs-helper-param-") as temp_name:
        extract_root = Path(temp_name) / "extract"
        result = mkpfs_main(
            [
                "unpack",
                str(image),
                str(extract_root),
                "--deep",
                "--only",
                "sce_sys/param.json",
                "--no-progress",
            ]
        )
        code = int(result or 0)
        if code != 0:
            return code
        candidates = [
            path
            for path in extract_root.rglob("param.json")
            if path.parent.name.casefold() == "sce_sys"
        ]
        if len(candidates) != 1:
            print(
                f"Expected one extracted sce_sys/param.json, found {len(candidates)}",
                file=sys.stderr,
            )
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidates[0], output)
        return 0


def _run_read_param_json(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: mkpfs-helper read-param-json IMAGE.ffpfsc OUTPUT.json", file=sys.stderr)
        return 2
    image = Path(argv[0]).resolve()
    output = Path(argv[1]).resolve()
    try:
        extract_param_json_low_memory(image, output)
    except LowMemoryMetadataUnavailable:
        return _fallback_extract_param_json(image, output)
    except (LowMemoryMetadataError, ExfatError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == _READ_PARAM_COMMAND:
        return _run_read_param_json(args[1:])
    return int(mkpfs_main(args) or 0)


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
