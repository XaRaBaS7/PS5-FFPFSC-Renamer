from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .ffpfsc_reader import _mkpfs_command
from .metadata import GameMetadata
from .process_utils import run_hidden

_PPSA_SEARCH_RE = re.compile(r"(?<![A-Z0-9])(PPSA[0-9]{5})(?![0-9])", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"^[\s._\-–—\[\]()]+|[\s._\-–—\[\]()]+$")


@dataclass(frozen=True, slots=True)
class InferredMetadata:
    metadata: GameMetadata
    source: str


def _find_ppsa(text: str) -> str | None:
    match = _PPSA_SEARCH_RE.search(text.upper())
    return match.group(1).upper() if match else None


def _clean_title(text: str, title_id: str | None) -> str | None:
    value = text
    if title_id:
        value = re.sub(re.escape(title_id), " ", value, flags=re.IGNORECASE)
    value = _SEPARATOR_RE.sub("", value.strip())
    value = re.sub(r"\s{2,}", " ", value).strip()
    if not value or _find_ppsa(value) == value.upper():
        return None
    return value


def infer_metadata_from_path(
    image: Path,
    *,
    library_root: Path | None = None,
) -> InferredMetadata | None:
    """Infer only obvious metadata from a filename/folder.

    This is deliberately a display-only fallback. It does not prove that the
    image contains the inferred metadata and must not be used as a verified
    metadata source for automatic rename operations.
    """
    image = Path(image)
    stem = image.stem
    parent_name = image.parent.name

    title_id = _find_ppsa(stem) or _find_ppsa(parent_name)
    if title_id is None:
        return None

    title_from_file = _clean_title(stem, title_id)
    title_from_folder: str | None = None

    use_parent = True
    if library_root is not None:
        try:
            use_parent = image.parent.resolve() != Path(library_root).resolve()
        except OSError:
            use_parent = image.parent != Path(library_root)

    if use_parent:
        title_from_folder = _clean_title(parent_name, title_id)

    title = title_from_file or title_from_folder
    source_bits = ["filename"]
    if title_from_folder and not title_from_file:
        source_bits.append("folder")

    return InferredMetadata(
        metadata=GameMetadata(title_id=title_id, title_name=title),
        source=" + ".join(source_bits),
    )


def classify_reader_error(detail: str) -> tuple[str, str]:
    """Return a stable code plus a short user-facing explanation."""
    lowered = detail.lower()

    if "truncated read at offset 0" in lowered:
        return (
            "truncated-read",
            "MkPFS could not read the image structure from the beginning of the file. "
            "The file may be incomplete/corrupt or may use a layout this MkPFS version does not understand.",
        )
    if "no inner exfat found" in lowered:
        return (
            "no-inner-exfat",
            "MkPFS did not find the wrapped exFAT layout used by the fast metadata reader. "
            "The image may use a direct/raw PFS layout or another compatible variant.",
        )
    if "timed out" in lowered:
        return (
            "timeout",
            "Metadata analysis timed out before MkPFS completed the requested inspection.",
        )
    if "traceback" in lowered:
        return (
            "mkpfs-error",
            "MkPFS stopped with an internal parsing error while inspecting this image.",
        )
    return (
        "metadata-read-error",
        "The internal sce_sys/param.json metadata could not be read with the current fast reader.",
    )


def _human_size(size: int) -> str:
    value = float(size)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"


def _run(command: list[str], timeout: int) -> tuple[int, str]:
    try:
        completed = run_hidden(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout} seconds"
    except OSError as exc:
        return 127, f"Unable to launch MkPFS: {exc}"

    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode, output


def _compact_output(text: str, limit: int = 2200) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return "…\n" + text[-limit:]


def _inspection_summary(output: str) -> str | None:
    """Extract a few useful fields when inspect emitted JSON."""
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    interesting: list[str] = []
    for key in ("format", "version", "block_size", "compressed", "encrypted", "signed"):
        if key in payload:
            interesting.append(f"{key}: {payload[key]}")
    return ", ".join(interesting) or None


def diagnose_image(
    image: Path,
    *,
    library_root: Path | None = None,
    timeout: int = 30,
) -> str:
    """Run small, read-only MkPFS diagnostics for one image."""
    image = Path(image).expanduser().resolve()
    lines = ["FFPFSC DIAGNOSTICS", "", f"File: {image.name}", f"Path: {image}"]

    if not image.exists():
        lines.append("Result: SOURCE MISSING")
        return "\n".join(lines)
    if not image.is_file():
        lines.append("Result: NOT A FILE")
        return "\n".join(lines)

    try:
        size = image.stat().st_size
    except OSError as exc:
        lines.append(f"Result: unable to read file information: {exc}")
        return "\n".join(lines)

    lines.append(f"Size: {_human_size(size)} ({size:,} bytes)")
    if size == 0:
        lines.extend(("", "Result: ZERO-LENGTH FILE", "The image contains no data."))
        return "\n".join(lines)

    inferred = infer_metadata_from_path(image, library_root=library_root)
    if inferred:
        lines.extend(
            (
                f"Path fallback: {inferred.metadata.title_id}",
                f"Fallback title: {inferred.metadata.title_name or '-'}",
                f"Fallback source: {inferred.source}",
            )
        )
    else:
        lines.append("Path fallback: no PPSA detected")

    base = _mkpfs_command()
    inspect_code, inspect_output = _run(
        [*base, "inspect", "--format", "json", str(image)], timeout
    )
    tree_code, tree_output = _run([*base, "tree", "--deep", str(image)], timeout)

    combined = f"{inspect_output}\n{tree_output}".lower()
    if "truncated read at offset 0" in combined:
        layout = "UNREADABLE / TRUNCATED AT START"
    elif "no inner exfat found" in combined:
        layout = "PFS READABLE, WRAPPED exFAT NOT DETECTED"
    elif tree_code == 0:
        layout = "TREE READABLE"
    elif inspect_code == 0:
        layout = "IMAGE HEADER READABLE"
    else:
        layout = "NOT RECOGNIZED BY CURRENT MkPFS"

    lines.extend(
        (
            "",
            f"MkPFS inspect: {'OK' if inspect_code == 0 else f'FAILED ({inspect_code})'}",
            f"MkPFS tree --deep: {'OK' if tree_code == 0 else f'FAILED ({tree_code})'}",
            f"Layout assessment: {layout}",
        )
    )

    inspect_summary = _inspection_summary(inspect_output)
    if inspect_summary:
        lines.append(f"Inspect summary: {inspect_summary}")

    technical = []
    if inspect_code != 0 and inspect_output:
        technical.append("[inspect]\n" + _compact_output(inspect_output))
    if tree_code != 0 and tree_output:
        technical.append("[tree --deep]\n" + _compact_output(tree_output))
    elif "no inner exfat found" in tree_output.lower():
        technical.append("[tree --deep]\n" + _compact_output(tree_output))

    if technical:
        lines.extend(("", "Technical details:", "\n\n".join(technical)))

    return "\n".join(lines)
