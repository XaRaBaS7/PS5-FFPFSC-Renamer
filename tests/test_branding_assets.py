from __future__ import annotations

import binascii
import struct
import zlib

from ps5_ffpfsc_renamer.branding import BRAND_ICON_NAME, BRAND_LOGO_NAME, brand_asset_path


def _png_dimensions(path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    offset = 8
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    saw_iend = False

    while offset < len(data):
        assert offset + 12 <= len(data), "truncated PNG chunk header"
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        assert crc_end <= len(data), f"truncated PNG chunk {chunk_type!r}"

        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        actual_crc = binascii.crc32(chunk_type)
        actual_crc = binascii.crc32(payload, actual_crc) & 0xFFFFFFFF
        assert expected_crc == actual_crc, f"invalid PNG CRC in {chunk_type!r}"

        if chunk_type == b"IHDR":
            assert length == 13
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            assert compression == 0
            assert filter_method == 0
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"IEND":
            saw_iend = True
            break

        offset = crc_end

    assert saw_iend
    assert width is not None and height is not None
    assert bit_depth is not None and color_type is not None
    assert interlace == 0, "brand PNGs must remain non-interlaced"
    assert idat, "PNG is missing IDAT data"

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    decoded = zlib.decompress(bytes(idat))
    assert len(decoded) == (row_bytes + 1) * height, "decoded PNG payload has an invalid size"

    return width, height


def test_official_brand_assets_are_present_and_valid_pngs() -> None:
    icon = brand_asset_path(BRAND_ICON_NAME)
    logo = brand_asset_path(BRAND_LOGO_NAME)
    assert icon is not None
    assert logo is not None

    icon_width, icon_height = _png_dimensions(icon)
    logo_width, logo_height = _png_dimensions(logo)

    assert icon_width == icon_height
    assert icon_width >= 256
    assert logo_width >= logo_height * 3
