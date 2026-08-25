from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def build_icon() -> tuple[Path, Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    size = 512
    image = Image.new("RGBA", (size, size), (12, 9, 20, 255))
    draw = ImageDraw.Draw(image)

    # Dark rounded tile with a subtle purple border.
    draw.rounded_rectangle(
        (28, 28, size - 28, size - 28),
        radius=112,
        fill=(20, 15, 31, 255),
        outline=(154, 92, 255, 255),
        width=12,
    )

    # FFPFSC document shape.
    doc = (132, 92, 344, 416)
    draw.rounded_rectangle(doc, radius=28, fill=(37, 29, 53, 255), outline=(212, 184, 255, 255), width=10)
    draw.polygon([(276, 92), (344, 160), (276, 160)], fill=(117, 78, 170, 255))
    draw.line((276, 92, 276, 160, 344, 160), fill=(212, 184, 255, 255), width=10)

    # Metadata lines.
    for y, width in ((214, 126), (254, 154), (294, 108)):
        draw.rounded_rectangle((164, y, 164 + width, y + 14), radius=7, fill=(79, 225, 205, 255))

    # Rename arrows crossing the document, the visual identity of the app.
    accent = (185, 120, 255, 255)
    draw.line((94, 344, 386, 344), fill=accent, width=22)
    draw.polygon([(386, 344), (340, 309), (340, 379)], fill=accent)
    draw.line((418, 390, 126, 390), fill=(79, 225, 205, 255), width=18)
    draw.polygon([(126, 390), (168, 358), (168, 422)], fill=(79, 225, 205, 255))

    png_path = ASSETS / "app-icon.png"
    ico_path = ASSETS / "app-icon.ico"
    image.save(png_path, "PNG", optimize=True)
    image.save(
        ico_path,
        "ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return png_path, ico_path


if __name__ == "__main__":
    png, ico = build_icon()
    print(f"Generated {png}")
    print(f"Generated {ico}")
