from __future__ import annotations

import hashlib
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .metadata import GameMetadata
from .naming import FOLDER_FILE_ONLY, FOLDER_SMART, NamingOptions
from .operation_history import OperationHistory
from .rename_plan import PlanStatus, build_rename_plan
from .renamer import apply_rename_plan, build_forward_steps


@dataclass(frozen=True, slots=True)
class SelfTestCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class SelfTestReport:
    passed: bool
    checks: tuple[SelfTestCheck, ...]
    elapsed_seconds: float

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def as_text(self) -> str:
        lines = [
            "PS5 FFPFSC Renamer — Rename Safety Self-Test",
            f"Result: {'PASS' if self.passed else 'FAIL'}",
            f"Checks: {self.passed_count}/{len(self.checks)} passed",
            f"Elapsed: {self.elapsed_seconds:.3f}s",
            "",
        ]
        for check in self.checks:
            prefix = "PASS" if check.passed else "FAIL"
            lines.append(f"[{prefix}] {check.name}: {check.detail}")
        return "\n".join(lines)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload(label: str) -> bytes:
    seed = (f"PS5-FFPFSC-Renamer self-test::{label}\n" * 128).encode("utf-8")
    return seed + bytes(range(256))


def _assert_ready(plan) -> None:
    if len(plan) != 1 or plan[0].status is not PlanStatus.READY:
        state = plan[0].status.value if plan else "empty"
        reason = plan[0].reason if plan else "no plan item"
        raise AssertionError(f"expected READY plan, got {state}: {reason}")


def _file_only_case(root: Path) -> str:
    case = root / "file-only"
    case.mkdir()
    source = case / "Returnal Backup.ffpfsc"
    source.write_bytes(_payload("file-only"))
    original_hash = _digest(source)

    metadata = GameMetadata(
        title_id="PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )
    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_FILE_ONLY,
        library_roots=(str(case),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    _assert_ready(plan)
    destination = case / "PPSA01285.ffpfsc"
    if plan[0].destination != destination.resolve():
        raise AssertionError(f"unexpected destination: {plan[0].destination}")

    steps = build_forward_steps(plan)
    completed = apply_rename_plan(plan)
    if source.exists() or not destination.exists():
        raise AssertionError("file-only rename did not move the source to the planned destination")
    if _digest(destination) != original_hash:
        raise AssertionError("file content changed during file-only rename")

    history = OperationHistory(case / "history.sqlite3")
    transaction_id = history.record(label="Self-test file-only", pairs=completed, steps=steps)
    if not transaction_id:
        raise AssertionError("operation history did not record the file-only rename")
    history.undo(transaction_id)

    if not source.exists() or destination.exists():
        raise AssertionError("Undo did not restore the original file-only path")
    if _digest(source) != original_hash:
        raise AssertionError("file content changed after file-only Undo")
    return "rename + SHA-256 content check + Undo passed"


def _smart_loose_case(root: Path) -> str:
    case = root / "smart-loose"
    case.mkdir()
    source = case / "loose-name.ffpfsc"
    source.write_bytes(_payload("smart-loose"))
    original_hash = _digest(source)

    metadata = GameMetadata(title_id="PPSA54321", title_name="Smart Test")
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        folder_handling=FOLDER_SMART,
        library_roots=(str(case),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    _assert_ready(plan)
    item = plan[0]
    if item.target_directory is None or item.source_directory is not None:
        raise AssertionError("loose Smart item did not plan a new per-game folder")

    steps = build_forward_steps(plan)
    completed = apply_rename_plan(plan)
    if source.exists() or not item.destination.exists():
        raise AssertionError("Smart loose-file rename did not create/move to the planned path")
    if _digest(item.destination) != original_hash:
        raise AssertionError("file content changed during Smart loose-file rename")

    history = OperationHistory(case / "history.sqlite3")
    transaction_id = history.record(label="Self-test Smart loose", pairs=completed, steps=steps)
    if not transaction_id:
        raise AssertionError("operation history did not record Smart loose rename")
    history.undo(transaction_id)

    if not source.exists() or _digest(source) != original_hash:
        raise AssertionError("Smart loose Undo did not restore the original file unchanged")
    if item.target_directory.exists():
        raise AssertionError("empty app-created Smart folder remained after Undo")
    return "folder creation + move + SHA-256 content check + Undo passed"


def _smart_existing_folder_case(root: Path) -> str:
    case = root / "smart-existing"
    case.mkdir()
    source_folder = case / "Wrong Folder Name"
    source_folder.mkdir()
    source = source_folder / "old-file-name.ffpfsc"
    source.write_bytes(_payload("smart-existing"))
    original_hash = _digest(source)

    metadata = GameMetadata(title_id="PPSA11111", title_name="Folder Test")
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        folder_handling=FOLDER_SMART,
        library_roots=(str(case),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    _assert_ready(plan)
    item = plan[0]
    if item.source_directory != source_folder.resolve() or item.target_directory is None:
        raise AssertionError("existing Smart folder was not planned for a folder rename")

    steps = build_forward_steps(plan)
    completed = apply_rename_plan(plan)
    if source_folder.exists() or not item.destination.exists():
        raise AssertionError("Smart existing-folder transaction did not complete")
    if _digest(item.destination) != original_hash:
        raise AssertionError("file content changed during Smart folder rename")

    history = OperationHistory(case / "history.sqlite3")
    transaction_id = history.record(label="Self-test Smart existing", pairs=completed, steps=steps)
    if not transaction_id:
        raise AssertionError("operation history did not record Smart existing-folder rename")
    history.undo(transaction_id)

    if not source.exists() or _digest(source) != original_hash:
        raise AssertionError("Smart existing-folder Undo did not restore the original state")
    if item.target_directory.exists():
        raise AssertionError("renamed Smart folder still exists after Undo")
    return "folder rename + file rename + SHA-256 content check + Undo passed"


def _collision_case(root: Path) -> str:
    case = root / "collision"
    case.mkdir()
    source = case / "source.ffpfsc"
    target = case / "PPSA22222.ffpfsc"
    source_payload = _payload("collision-source")
    target_payload = _payload("collision-target")
    source.write_bytes(source_payload)
    target.write_bytes(target_payload)

    metadata = GameMetadata(title_id="PPSA22222")
    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_FILE_ONLY,
        library_roots=(str(case),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    if len(plan) != 1 or plan[0].status is not PlanStatus.COLLISION:
        raise AssertionError("existing destination was not blocked as COLLISION")
    if source.read_bytes() != source_payload or target.read_bytes() != target_payload:
        raise AssertionError("collision planning modified filesystem content")
    return "existing destination blocked without overwriting either file"


def _runtime_rollback_case(root: Path) -> str:
    case = root / "rollback"
    case.mkdir()
    first = case / "first.ffpfsc"
    second = case / "second.ffpfsc"
    first_payload = _payload("rollback-first")
    second_payload = _payload("rollback-second")
    first.write_bytes(first_payload)
    second.write_bytes(second_payload)

    items = [
        (first, GameMetadata(title_id="PPSA30001")),
        (second, GameMetadata(title_id="PPSA30002")),
    ]
    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_FILE_ONLY,
        library_roots=(str(case),),
    )
    plan = build_rename_plan(items, options)
    if len(plan) != 2 or any(item.status is not PlanStatus.READY for item in plan):
        raise AssertionError("rollback setup did not produce two READY items")

    # Simulate another process creating the second destination after preview
    # but before Apply. The first rename must be rolled back automatically.
    occupied = plan[1].destination
    occupied_payload = _payload("rollback-occupied")
    occupied.write_bytes(occupied_payload)

    try:
        apply_rename_plan(plan)
    except FileExistsError:
        pass
    else:
        raise AssertionError("runtime collision unexpectedly succeeded")

    if first.read_bytes() != first_payload:
        raise AssertionError("first file was not restored after later batch failure")
    if second.read_bytes() != second_payload:
        raise AssertionError("second source changed during failed batch")
    if occupied.read_bytes() != occupied_payload:
        raise AssertionError("runtime collision target was overwritten")
    if plan[0].destination.exists():
        raise AssertionError("first destination remained after automatic rollback")
    return "late collision triggered automatic rollback with all original bytes preserved"


def run_rename_safety_self_test() -> SelfTestReport:
    started = time.perf_counter()
    checks: list[SelfTestCheck] = []
    cases: tuple[tuple[str, Callable[[Path], str]], ...] = (
        ("File-only rename and Undo", _file_only_case),
        ("Smart loose-file folder creation and Undo", _smart_loose_case),
        ("Smart existing-folder rename and Undo", _smart_existing_folder_case),
        ("Collision protection", _collision_case),
        ("Batch rollback after late collision", _runtime_rollback_case),
    )

    with tempfile.TemporaryDirectory(prefix="ps5-ffpfsc-renamer-selftest-") as temp:
        root = Path(temp)
        for name, case in cases:
            try:
                detail = case(root)
            except Exception as exc:  # Self-test must report every case, not stop at the first failure.
                checks.append(SelfTestCheck(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}"))
            else:
                checks.append(SelfTestCheck(name=name, passed=True, detail=detail))

    elapsed = time.perf_counter() - started
    return SelfTestReport(
        passed=all(check.passed for check in checks),
        checks=tuple(checks),
        elapsed_seconds=elapsed,
    )
