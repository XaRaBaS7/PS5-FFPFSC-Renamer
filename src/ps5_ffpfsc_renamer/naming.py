from __future__ import annotations

import re
from dataclasses import dataclass

from .metadata import GameMetadata

COMPONENT_TITLE_ID = "title_id"
COMPONENT_TITLE = "title"
COMPONENT_VERSION = "version"
COMPONENTS = (COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION)

FOLDER_FILE_ONLY = "file_only"
FOLDER_SMART = "smart"
FOLDER_ALWAYS_NEW = "always_new"
FOLDER_HANDLING_MODES = (FOLDER_FILE_ONLY, FOLDER_SMART, FOLDER_ALWAYS_NEW)

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
    # Backward-compatible flag used by the older UI/tests. When True and
    # folder_handling is left at file_only it maps to always_new.
    create_folder: bool = False
    folder_handling: str = FOLDER_FILE_ONLY
    # Backward-compatible single selected root.
    library_root: str | None = None
    # Current UI can scan multiple independent roots. Smart mode resolves the
    # correct protected root separately for every source path.
    library_roots: tuple[str, ...] = ()
    separator: str = " - "
    component_order: tuple[str, ...] = COMPONENTS


def effective_folder_handling(options: NamingOptions) -> str:
    mode = options.folder_handling
    if mode not in FOLDER_HANDLING_MODES:
        raise ValueError(f"Unknown folder handling mode: {mode}")
    if mode == FOLDER_FILE_ONLY and options.create_folder:
        return FOLDER_ALWAYS_NEW
    return mode


def sanitize_windows_component(value: str) -> str:
    """Return a safe Windows filename/directory component."""
    cleaned = _INVALID_CHARS_RE.sub(" ", value)
    cleaned = _SPACE_RE.sub(" ", cleaned).strip().rstrip(". ")
    if not cleaned:
        return "Unknown"
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:180].rstrip(". ") or "Unknown"


def compact_ps5_version(value: str | None) -> str | None:
    """Convert common PS5 versions to a human-friendly form.

    Examples:
        01.000.000 -> 1.0
        02.500.000 -> 2.5
        01.250.000 -> 1.25
        01.005.000 -> 1.005
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

    minor = parts[1].rstrip("0") or "0"
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


def _validated_component_order(order: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for component in order:
        if component not in COMPONENTS:
            raise ValueError(f"Unknown filename component: {component}")
        if component in seen:
            raise ValueError(f"Duplicate filename component: {component}")
        seen.add(component)
        normalized.append(component)

    for component in COMPONENTS:
        if component not in seen:
            normalized.append(component)
    return tuple(normalized)


def build_output_stem(metadata: GameMetadata, options: NamingOptions) -> str:
    values: dict[str, str | None] = {
        COMPONENT_TITLE_ID: metadata.title_id if options.include_title_id else None,
        COMPONENT_TITLE: (
            sanitize_windows_component(metadata.title_name)
            if options.include_title and metadata.title_name
            else None
        ),
        COMPONENT_VERSION: None,
    }

    if options.include_version:
        version = display_version(metadata, compact=options.compact_version)
        if version:
            version_text = f"v{version}" if options.version_prefix else version
            values[COMPONENT_VERSION] = sanitize_windows_component(version_text)

    parts: list[str] = []
    for component in _validated_component_order(options.component_order):
        value = values.get(component)
        if value:
            parts.append(value)

    if not parts:
        raise ValueError("Output format must include at least one available filename component")

    return sanitize_windows_component(options.separator.join(parts))


def example_output(options: NamingOptions) -> str:
    metadata = GameMetadata(
        title_id="PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
        master_version="01.00",
    )
    stem = build_output_stem(metadata, options)
    filename = f"{stem}.ffpfsc"
    if effective_folder_handling(options) != FOLDER_FILE_ONLY:
        return f"{stem}\\{filename}"
    return filename
