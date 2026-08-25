from __future__ import annotations

import argparse
from pathlib import Path

from .ffpfsc_reader import MetadataReadError, read_metadata
from .rename_plan import build_rename_plan
from .renamer import apply_rename_plan
from .scanner import scan_ffpfsc


def _collect(path: Path, recursive: bool) -> tuple[list[tuple[Path, object]], int]:
    found = scan_ffpfsc(path, recursive=recursive)
    parsed: list[tuple[Path, object]] = []
    failures = 0
    for image in found:
        try:
            metadata = read_metadata(image)
        except MetadataReadError as exc:
            failures += 1
            print(f"ERROR  {image.name}: {exc}")
            continue
        parsed.append((image, metadata))
    return parsed, failures


def _print_plan(parsed: list[tuple[Path, object]]) -> list:
    plan = build_rename_plan(parsed)  # type: ignore[arg-type]
    for item in plan:
        title = item.metadata.title_name or "-"
        version = item.metadata.content_version or "-"
        print(
            f"{item.status.value.upper():9} {item.source.name} -> {item.destination.name} | "
            f"{item.metadata.title_id} | {version} | {title}"
        )
        if item.reason:
            print(f"           reason: {item.reason}")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ps5-ffpfsc-renamer")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("scan", "rename"):
        command = sub.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--no-recursive", action="store_true")

    args = parser.parse_args(argv)
    parsed, failures = _collect(args.path, recursive=not args.no_recursive)
    plan = _print_plan(parsed)

    if args.command == "rename":
        blocked = [item for item in plan if not item.can_apply and item.status.value not in {"unchanged"}]
        if blocked or failures:
            print("Rename aborted: resolve scan errors or collisions first.")
            return 2
        completed = apply_rename_plan(plan)
        print(f"Renamed {len(completed)} file(s).")

    return 1 if failures else 0
