from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ffpfsc_reader import (
    MetadataReadCancelled,
    MetadataReadError,
    _mkpfs_command,
    _stop_process,
)
from .metadata import GameMetadata, metadata_from_param_json
from .process_utils import hidden_subprocess_kwargs

_CACHE_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class GameDetails:
    image: Path
    metadata: GameMetadata
    param_json: dict[str, Any]
    icon_path: Path | None
    cache_hit: bool


@dataclass(frozen=True, slots=True)
class DetailsCacheStats:
    entries: int = 0
    valid_entries: int = 0
    stale_entries: int = 0
    bytes_on_disk: int = 0


def default_details_cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "PS5-FFPFSC-Renamer" if base else Path.home() / ".ps5-ffpfsc-renamer"
    path = root / "details-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _identity(image: Path) -> tuple[int, int]:
    stat = image.stat()
    return int(stat.st_size), int(stat.st_mtime_ns)


def details_cache_key(image: Path) -> str:
    resolved = image.resolve(strict=False)
    size, mtime_ns = _identity(resolved)
    payload = f"{str(resolved).casefold()}\0{size}\0{mtime_ns}".encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(payload).hexdigest()


def _cache_dir(image: Path, cache_root: Path | None = None) -> Path:
    root = cache_root or default_details_cache_root()
    return root / details_cache_key(image)


def _load_cached(image: Path, cache_root: Path | None = None) -> GameDetails | None:
    folder = _cache_dir(image, cache_root)
    param_path = folder / "param.json"
    manifest_path = folder / "manifest.json"
    if not param_path.is_file() or not manifest_path.is_file():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data = json.loads(param_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(manifest, dict) or manifest.get("schema") != _CACHE_SCHEMA:
        return None
    if not isinstance(data, dict):
        return None

    try:
        metadata = metadata_from_param_json(data)
    except ValueError:
        return None

    icon = folder / "icon0.png"
    return GameDetails(
        image=image,
        metadata=metadata,
        param_json=data,
        icon_path=icon if icon.is_file() else None,
        cache_hit=True,
    )


def _run_unpack(
    image: Path,
    output_dir: Path,
    selectors: tuple[str, ...],
    *,
    timeout: int,
    cancel_event: threading.Event | None,
) -> None:
    command = [*_mkpfs_command(), "unpack", str(image), str(output_dir), "--deep"]
    for selector in selectors:
        command.extend(("--only", selector))
    command.append("--no-progress")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **hidden_subprocess_kwargs(),
        )
    except OSError as exc:
        raise MetadataReadError(f"Unable to run MkPFS: {exc}") from exc

    deadline = time.monotonic() + timeout
    stdout = ""
    stderr = ""
    while True:
        if cancel_event is not None and cancel_event.is_set():
            _stop_process(process)
            raise MetadataReadCancelled("Game details analysis cancelled")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            raise MetadataReadError(f"MkPFS timed out after {timeout} seconds")
        try:
            stdout, stderr = process.communicate(timeout=min(0.25, remaining))
            break
        except subprocess.TimeoutExpired:
            continue

    if process.returncode != 0:
        detail = (stderr or stdout).strip()
        raise MetadataReadError(detail or f"MkPFS exited with code {process.returncode}")


def _find_asset(output_dir: Path, filename: str) -> Path | None:
    wanted = filename.casefold()
    for path in output_dir.rglob("*"):
        if not path.is_file() or path.name.casefold() != wanted:
            continue
        if path.parent.name.casefold() == "sce_sys":
            return path
    return None


def _write_cache(
    image: Path,
    data: dict[str, Any],
    icon: Path | None,
    cache_root: Path | None = None,
) -> tuple[Path, Path | None]:
    folder = _cache_dir(image, cache_root)
    folder.mkdir(parents=True, exist_ok=True)

    param_path = folder / "param.json"
    temporary = folder / "param.json.tmp"
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(param_path)

    icon_target: Path | None = None
    if icon is not None and icon.is_file():
        icon_target = folder / "icon0.png"
        shutil.copy2(icon, icon_target)
    else:
        try:
            (folder / "icon0.png").unlink(missing_ok=True)
        except OSError:
            pass

    size, mtime_ns = _identity(image)
    manifest = {
        "schema": _CACHE_SCHEMA,
        "source": str(image.resolve(strict=False)),
        "size": size,
        "mtime_ns": mtime_ns,
    }
    manifest_tmp = folder / "manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_tmp.replace(folder / "manifest.json")
    return param_path, icon_target


def load_game_details(
    image: Path,
    *,
    timeout: int = 120,
    cancel_event: threading.Event | None = None,
    cache_root: Path | None = None,
    force: bool = False,
) -> GameDetails:
    image = image.resolve(strict=False)
    if not image.is_file():
        raise MetadataReadError(f"File not found: {image}")
    if image.suffix.casefold() != ".ffpfsc":
        raise MetadataReadError(f"Unsupported file extension: {image.suffix}")
    if cancel_event is not None and cancel_event.is_set():
        raise MetadataReadCancelled("Game details analysis cancelled")

    if not force:
        cached = _load_cached(image, cache_root)
        if cached is not None:
            return cached

    with tempfile.TemporaryDirectory(prefix="ps5-ffpfsc-details-") as temp_name:
        output_dir = Path(temp_name) / "extract"

        # MkPFS supports repeated --only selectors. Some unusual images may
        # reject the combined selector set, so retry param.json alone before
        # declaring the details view unavailable.
        try:
            _run_unpack(
                image,
                output_dir,
                ("sce_sys/param.json", "sce_sys/icon0.png"),
                timeout=timeout,
                cancel_event=cancel_event,
            )
        except MetadataReadError as combined_error:
            shutil.rmtree(output_dir, ignore_errors=True)
            try:
                _run_unpack(
                    image,
                    output_dir,
                    ("sce_sys/param.json",),
                    timeout=timeout,
                    cancel_event=cancel_event,
                )
            except MetadataReadError:
                raise combined_error

        param_path = _find_asset(output_dir, "param.json")
        if param_path is None:
            raise MetadataReadError("sce_sys/param.json was not found in the selective extraction")

        try:
            data = json.loads(param_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MetadataReadError(f"Invalid extracted param.json: {exc}") from exc
        if not isinstance(data, dict):
            raise MetadataReadError("param.json root is not a JSON object")

        try:
            metadata = metadata_from_param_json(data)
        except ValueError as exc:
            raise MetadataReadError(str(exc)) from exc

        icon = _find_asset(output_dir, "icon0.png")
        _, cached_icon = _write_cache(image, data, icon, cache_root)
        return GameDetails(
            image=image,
            metadata=metadata,
            param_json=data,
            icon_path=cached_icon,
            cache_hit=False,
        )


def _directory_size(folder: Path) -> int:
    total = 0
    try:
        paths = folder.rglob("*")
        for path in paths:
            try:
                if path.is_file():
                    total += int(path.stat().st_size)
            except OSError:
                continue
    except OSError:
        pass
    return total


def _cache_entry_is_valid(folder: Path) -> bool:
    manifest_path = folder / "manifest.json"
    param_path = folder / "param.json"
    if not manifest_path.is_file() or not param_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict) or manifest.get("schema") != _CACHE_SCHEMA:
        return False
    source_text = manifest.get("source")
    if not isinstance(source_text, str) or not source_text.strip():
        return False
    source = Path(source_text)
    try:
        size, mtime_ns = _identity(source)
    except OSError:
        return False
    try:
        expected_size = int(manifest.get("size"))
        expected_mtime = int(manifest.get("mtime_ns"))
    except (TypeError, ValueError):
        return False
    return size == expected_size and mtime_ns == expected_mtime


def details_cache_stats(cache_root: Path | None = None) -> DetailsCacheStats:
    root = cache_root or default_details_cache_root()
    if not root.exists():
        return DetailsCacheStats()
    entries = 0
    valid = 0
    stale = 0
    bytes_on_disk = 0
    try:
        children = list(root.iterdir())
    except OSError:
        return DetailsCacheStats()
    for child in children:
        if not child.is_dir():
            continue
        entries += 1
        bytes_on_disk += _directory_size(child)
        if _cache_entry_is_valid(child):
            valid += 1
        else:
            stale += 1
    return DetailsCacheStats(
        entries=entries,
        valid_entries=valid,
        stale_entries=stale,
        bytes_on_disk=bytes_on_disk,
    )


def prune_details_cache(cache_root: Path | None = None) -> int:
    root = cache_root or default_details_cache_root()
    if not root.exists():
        return 0
    removed = 0
    try:
        children = list(root.iterdir())
    except OSError:
        return 0
    for child in children:
        if not child.is_dir() or _cache_entry_is_valid(child):
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError:
            pass
    return removed


def clear_details_cache(cache_root: Path | None = None) -> int:
    root = cache_root or default_details_cache_root()
    if not root.exists():
        return 0
    removed = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError:
            pass
    return removed
