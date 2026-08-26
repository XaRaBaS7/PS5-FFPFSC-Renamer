from __future__ import annotations

import ast
from pathlib import Path


UI_ROOT = Path(__file__).resolve().parents[1] / "src" / "ps5_ffpfsc_renamer" / "ui"


def _is_versioned_gui_module(name: str) -> bool:
    return any(part.startswith("gui_v") for part in name.split("."))


def test_canonical_ui_modules_do_not_import_versioned_gui_layers() -> None:
    offenders: list[str] = []
    for path in sorted(UI_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_versioned_gui_module(alias.name):
                        offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if _is_versioned_gui_module(node.module):
                    offenders.append(
                        f"{path.name}:{node.lineno} from {node.module} import ..."
                    )

    assert not offenders, "Versioned GUI imports found in canonical ui/:\n" + "\n".join(offenders)
