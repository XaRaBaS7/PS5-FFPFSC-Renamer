from __future__ import annotations

import struct

from ps5_ffpfsc_renamer.branding import BRAND_ICON_NAME, BRAND_LOGO_NAME, brand_asset_path


def _png_dimensions(path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


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
