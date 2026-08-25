from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PREVIEW = "docs/screenshots/app-preview.svg"
GUI_PREFIXES = (
    "src/ps5_ffpfsc_renamer/gui",
    "src/ps5_ffpfsc_renamer/theme.py",
    "src/ps5_ffpfsc_renamer/ui_icons.py",
)


def _run(*args: str) -> str:
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def _base_ref() -> str:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    base = os.environ.get("GITHUB_BASE_REF", "")

    if event == "pull_request" and base:
        return f"origin/{base}"
    if branch == "main":
        return "HEAD^"
    return "origin/main"


def main() -> int:
    if not Path(PREVIEW).is_file():
        print(f"ERROR: canonical README preview is missing: {PREVIEW}")
        return 1

    base = _base_ref()
    try:
        changed = _run("git", "diff", "--name-only", f"{base}...HEAD").splitlines()
    except subprocess.CalledProcessError:
        # Main push compares the release commit directly with its parent.
        try:
            changed = _run("git", "diff", "--name-only", "HEAD^", "HEAD").splitlines()
        except subprocess.CalledProcessError as exc:
            print(f"WARNING: unable to determine changed files: {exc}")
            return 0

    visible_change = any(
        path.startswith(GUI_PREFIXES[0])
        or path == GUI_PREFIXES[1]
        or path == GUI_PREFIXES[2]
        for path in changed
    )
    preview_changed = PREVIEW in changed

    if visible_change and not preview_changed:
        print("ERROR: visible GUI files changed but the README preview was not refreshed.")
        print(f"Update {PREVIEW} in the same PR/commit.")
        print("See docs/SCREENSHOT_POLICY.md.")
        return 1

    if visible_change:
        print("README preview check: GUI changed and preview was refreshed.")
    else:
        print("README preview check: no visible GUI change detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
