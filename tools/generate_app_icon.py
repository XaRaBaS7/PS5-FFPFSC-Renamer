from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "brand" / "app-symbol.png"


def build_icon() -> tuple[Path, Path]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Official brand icon is missing: {SOURCE}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as source:
        image = source.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)

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
    print(f"Generated {png} from {SOURCE}")
    print(f"Generated {ico} from {SOURCE}")
