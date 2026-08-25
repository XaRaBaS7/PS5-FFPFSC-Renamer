from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .cache import MetadataCache
from .metadata import GameMetadata, metadata_from_param_json
from .process_utils import hidden_subprocess_kwargs


class MetadataReadError(RuntimeError):
    pass


class MetadataReadCancelled(MetadataReadError):
    pass


_default_cache: MetadataCache | None = None
_default_cache_lock = threading.Lock()
_custom_mkpfs_executable: Path | None = None


def _get_default_cache() -> MetadataCache:
    global _default_cache
    if _default_cache is None:
        with _default_cache_lock:
            if _default_cache is None:
                _default_cache = MetadataCache()
    return _default_cache


def set_mkpfs_executable(path: str | Path | None) -> Path | None:
    """Set an optional MkPFS executable override for the current process.

    Passing ``None`` restores automatic discovery. An invalid path is retained
    as ``None`` so the bundled helper/PATH/Python fallback can still be used.
    """
    global _custom_mkpfs_executable
    if path is None or not str(path).strip():
        _custom_mkpfs_executable = None
        return None
    candidate = Path(path).expanduser()
    try:
        candidate = candidate.resolve(strict=False)
    except OSError:
        candidate = candidate.absolute()
    _custom_mkpfs_executable = candidate if candidate.is_file() else None
    return _custom_mkpfs_executable


def get_mkpfs_executable() -> Path | None:
    return _custom_mkpfs_executable


def _bundled_mkpfs_helper() -> Path | None:
    """Return the sibling helper executable used by PyInstaller releases."""
    if not getattr(sys, "frozen", False):
        return None
    base = Path(sys.executable).resolve().parent
    candidates = (
        base / "mkpfs-helper.exe",
        base / "mkpfs-helper",
        base / "tools" / "mkpfs-helper.exe",
        base / "tools" / "mkpfs-helper",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def mkpfs_source_description() -> str:
    """Return a short description of the executable MkPFS source in use."""
    if _custom_mkpfs_executable is not None and _custom_mkpfs_executable.is_file():
        return f"Custom: {_custom_mkpfs_executable}"
    helper = _bundled_mkpfs_helper()
    if helper is not None:
        return f"Bundled helper: {helper}"
    executable = shutil.which("mkpfs")
    if executable:
        return f"PATH: {executable}"
    if not getattr(sys, "frozen", False) and importlib.util.find_spec("mkpfs") is not None:
        return "Python module: mkpfs"
    return "Not available"


def mkpfs_available() -> bool:
    """Return True when MkPFS can be launched from this environment."""
    if _custom_mkpfs_executable is not None and _custom_mkpfs_executable.is_file():
        return True
    helper = _bundled_mkpfs_helper()
    executable = shutil.which("mkpfs")
    if getattr(sys, "frozen", False):
        return helper is not None or executable is not None
    return executable is not None or importlib.util.find_spec("mkpfs") is not None


def _mkpfs_command() -> list[str]:
    if _custom_mkpfs_executable is not None and _custom_mkpfs_executable.is_file():
        return [str(_custom_mkpfs_executable)]

    helper = _bundled_mkpfs_helper()
    if helper is not None:
        return [str(helper)]

    executable = shutil.which("mkpfs")
    if executable:
        return [executable]

    # In a normal Python environment, launching ``python -m mkpfs`` keeps the
    # metadata parser isolated and cancellable. Do not use sys.executable this
    # way in a frozen app: there it points to the GUI executable, not Python.
    if not getattr(sys, "frozen", False) and importlib.util.find_spec("mkpfs") is not None:
        return [sys.executable, "-m", "mkpfs"]

    if getattr(sys, "frozen", False):
        raise MetadataReadError(
            "The bundled MkPFS helper is missing and no custom executable is configured. "
            "Reinstall/extract the complete PS5 FFPFSC Renamer release folder."
        )
    raise MetadataReadError(
        "MkPFS is not installed. Install it with: python -m pip install mkpfs==0.0.9"
    )


def _stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    """Terminate a child process and return any captured output."""
    if process.poll() is None:
        process.terminate()
    try:
        return process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.communicate()


def read_metadata(
    image: Path,
    timeout: int = 120,
    cancel_event: threading.Event | None = None,
    *,
    cache: MetadataCache | None = None,
    use_cache: bool = True,
) -> GameMetadata:
    image = image.resolve()
    if not image.is_file():
        raise MetadataReadError(f"File not found: {image}")
    if image.suffix.lower() != ".ffpfsc":
        raise MetadataReadError(f"Unsupported file extension: {image.suffix}")
    if cancel_event is not None and cancel_event.is_set():
        raise MetadataReadCancelled("Metadata analysis cancelled")

    active_cache: MetadataCache | None = None
    if use_cache:
        try:
            active_cache = cache or _get_default_cache()
            cached = active_cache.lookup(image)
            if cached.hit and cached.metadata is not None:
                return cached.metadata
        except Exception:
            active_cache = None

    with tempfile.TemporaryDirectory(prefix="ps5-ffpfsc-renamer-") as temp_name:
        output_dir = Path(temp_name) / "extract"
        command = [
            *_mkpfs_command(),
            "unpack",
            str(image),
            str(output_dir),
            "--deep",
            "--only",
            "sce_sys/param.json",
            "--no-progress",
        ]

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
                raise MetadataReadCancelled("Metadata analysis cancelled")

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

        candidates = list(output_dir.rglob("param.json"))
        candidates = [p for p in candidates if p.parent.name.lower() == "sce_sys"]
        if len(candidates) != 1:
            raise MetadataReadError(
                f"Expected one extracted sce_sys/param.json, found {len(candidates)}"
            )

        try:
            with candidates[0].open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise MetadataReadError(f"Invalid extracted param.json: {exc}") from exc

        if not isinstance(data, dict):
            raise MetadataReadError("param.json root is not a JSON object")

        try:
            metadata = metadata_from_param_json(data)
        except ValueError as exc:
            raise MetadataReadError(str(exc)) from exc

        if active_cache is not None:
            try:
                active_cache.store(image, metadata)
            except Exception:
                pass

        return metadata
