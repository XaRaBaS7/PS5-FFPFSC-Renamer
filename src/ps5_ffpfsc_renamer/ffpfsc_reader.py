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

from .metadata import GameMetadata, metadata_from_param_json


class MetadataReadError(RuntimeError):
    pass


class MetadataReadCancelled(MetadataReadError):
    pass


def mkpfs_available() -> bool:
    """Return True when MkPFS can be launched from this Python environment."""
    return shutil.which("mkpfs") is not None or importlib.util.find_spec("mkpfs") is not None


def _mkpfs_command() -> list[str]:
    executable = shutil.which("mkpfs")
    if executable:
        return [executable]
    if importlib.util.find_spec("mkpfs") is not None:
        return [sys.executable, "-m", "mkpfs"]
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
) -> GameMetadata:
    image = image.resolve()
    if not image.is_file():
        raise MetadataReadError(f"File not found: {image}")
    if image.suffix.lower() != ".ffpfsc":
        raise MetadataReadError(f"Unsupported file extension: {image.suffix}")
    if cancel_event is not None and cancel_event.is_set():
        raise MetadataReadCancelled("Metadata analysis cancelled")

    with tempfile.TemporaryDirectory(prefix="ps5-ffpfsc-renamer-") as temp_name:
        # MkPFS 0.0.9 expects the output path not to exist unless
        # --overwrite is supplied. Keep the TemporaryDirectory as a private
        # parent and hand MkPFS a child path that has not been created yet.
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
            return metadata_from_param_json(data)
        except ValueError as exc:
            raise MetadataReadError(str(exc)) from exc
