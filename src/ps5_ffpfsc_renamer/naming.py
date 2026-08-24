from __future__ import annotations

import re
from dataclasses import dataclass

from .metadata import GameMetadata

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class NamingOptions:
    include_title_id: bool = True
    include_title: bool = False
    include_version: bool = False
    compact_version: bool = True
    version_prefix: bool = True
    create_folder: bool = False
    separator: str = " - "


def sanitize_windows_component(value: str) -> str:
    """Return a safe Windows filename/directory component."""
    cleaned = _INVALID_CHARS_RE.sub(" ", value)
    cleaned = _SPACE_RE.sub(" ", cleaned).strip().rstrip(". ")
    if not cleaned:
        return "Unknown"
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    # Leave room for extension/path handling and avoid pathological components.
    return cleaned[:180].rstrip(". ") or "Unknown"


def compact_ps5_version(value: str | None) -> str | None:
    """Convert common PS5 versions to a human-friendly form.

    Examples:
        01.000.000 -> 1.0
        02.500.000 -> 2.5
        01.250.000 -> 1.25
        01.000.001 -> 1.0.1
    """
    if not value:
        return None
    raw = value.strip()
    parts = raw.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return raw

    major = str(int(parts[0]))
    if len(parts) == 1:
        return major

    minor_raw = parts[1]
    minor = minor_raw.lstrip("0")
    if not minor:
        minor = "0"
    else:
        # PS5's fixed-width fractional group uses trailing zero padding.
        minor = minor.rstrip("0") or "0"

    result = f"{major}.{minor}"
    for extra in parts[2:]:
        if int(extra) != 0:
            result += f".{int(extra)}"
    return result


def display_version(metadata: GameMetadata, compact: bool = True) -> str | None:
    value = metadata.content_version or metadata.master_version
    if not value:
        return None
    return compact_ps5_version(value) if compact else value.strip()


def build_output_stem(metadata: GameMetadata, options: NamingOptions) -> str:
    parts: list[str] = []

    if options.include_title_id:
        parts.append(metadata.title_id)

    if options.include_title and metadata.title_name:
        parts.append(sanitize_windows_component(metadata.title_name))

    if options.include_version:
        version = display_version(metadata, compact=options.compact_version)
        if version:
            version_text = f"v{version}" if options.version_prefix else version
            parts.append(sanitize_windows_component(version_text))

    if not parts:
        raise ValueError("Output format must include at least one available filename component")

    stem = options.separator.join(parts)
    return sanitize_windows_component(stem)


def example_output(options: NamingOptions) -> str:
    metadata = GameMetadata(
        title_id="PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
        master_version="01.00",
    )
    stem = build_output_stem(metadata, options)
    filename = f"{stem}.ffpfsc"
    if options.create_folder:
        return f"{stem}\\{filename}"
    return filename
