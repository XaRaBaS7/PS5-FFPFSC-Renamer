from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .metadata import GameMetadata, metadata_from_param_json


class MetadataReadError(RuntimeError):
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


def read_metadata(image: Path, timeout: int = 120) -> GameMetadata:
    image = image.resolve()
    if not image.is_file():
        raise MetadataReadError(f"File not found: {image}")
    if image.suffix.lower() != ".ffpfsc":
        raise MetadataReadError(f"Unsupported file extension: {image.suffix}")

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
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MetadataReadError(f"Unable to run MkPFS: {exc}") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise MetadataReadError(detail or f"MkPFS exited with code {completed.returncode}")

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
