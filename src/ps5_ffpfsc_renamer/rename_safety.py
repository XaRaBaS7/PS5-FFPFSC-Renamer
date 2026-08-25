from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cache import quick_fingerprint
from .rename_plan import PlanStatus, RenamePlanItem


@dataclass(frozen=True, slots=True)
class FileIdentity:
    size: int
    device: int
    inode: int
    fallback_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class PreflightReport:
    ready_count: int
    blocked_count: int
    total_bytes: int
    file_renames: int
    directories_created: int
    directories_renamed: int
    identities: tuple[tuple[Path, FileIdentity], ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def can_apply(self) -> bool:
        return self.ready_count > 0 and not self.errors

    @property
    def total_gib(self) -> float:
        return self.total_bytes / (1024 ** 3)


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    source: Path
    destination: Path
    detail: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    checked_count: int
    verified_count: int
    issues: tuple[VerificationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.issues and self.checked_count == self.verified_count


def capture_file_identity(path: Path) -> FileIdentity:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    inode = int(getattr(stat, "st_ino", 0) or 0)
    device = int(getattr(stat, "st_dev", 0) or 0)
    fallback: str | None = None
    if inode == 0:
        fallback = quick_fingerprint(resolved)
    return FileIdentity(
        size=int(stat.st_size),
        device=device,
        inode=inode,
        fallback_fingerprint=fallback,
    )


def _identity_matches(path: Path, identity: FileIdentity) -> tuple[bool, str]:
    try:
        stat = Path(path).stat()
    except OSError as exc:
        return False, f"destination cannot be read: {exc}"

    if int(stat.st_size) != identity.size:
        return False, f"size changed from {identity.size} to {int(stat.st_size)} bytes"

    inode = int(getattr(stat, "st_ino", 0) or 0)
    device = int(getattr(stat, "st_dev", 0) or 0)
    if identity.inode and inode:
        if identity.inode != inode or identity.device != device:
            return False, "filesystem file identity changed during rename"
        return True, "same filesystem object"

    if identity.fallback_fingerprint is None:
        return True, "size preserved; filesystem identity unavailable"
    try:
        fingerprint = quick_fingerprint(Path(path))
    except OSError as exc:
        return False, f"fallback fingerprint failed: {exc}"
    if fingerprint != identity.fallback_fingerprint:
        return False, "sampled fingerprint changed during rename"
    return True, "sampled fingerprint preserved"


def preflight_rename(plan: list[RenamePlanItem]) -> PreflightReport:
    ready = [item for item in plan if item.status is PlanStatus.READY]
    blocked = [item for item in plan if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}]
    errors: list[str] = []
    warnings: list[str] = []
    identities: list[tuple[Path, FileIdentity]] = []
    total_bytes = 0
    file_renames = 0
    directories_created = 0
    directories_renamed = 0

    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()

    for item in ready:
        source = item.source.resolve()
        destination = item.destination.resolve()
        source_key = str(source).casefold()
        destination_key = str(destination).casefold()

        if source_key in seen_sources:
            errors.append(f"duplicate source in plan: {source}")
            continue
        seen_sources.add(source_key)
        if destination_key in seen_destinations:
            errors.append(f"duplicate destination in plan: {destination}")
            continue
        seen_destinations.add(destination_key)

        if not source.exists() or not source.is_file():
            errors.append(f"source missing before rename: {source}")
            continue
        if destination.exists() and destination_key != source_key:
            errors.append(f"destination appeared after preview: {destination}")
            continue

        try:
            identity = capture_file_identity(source)
        except OSError as exc:
            errors.append(f"cannot capture source identity for {source}: {exc}")
            continue
        identities.append((source, identity))
        total_bytes += identity.size

        if destination_key != source_key:
            file_renames += 1
        if item.source_directory is not None and item.target_directory is not None:
            directories_renamed += 1
        elif item.target_directory is not None:
            directories_created += 1

        try:
            if source.drive and destination.drive and source.drive.casefold() != destination.drive.casefold():
                warnings.append(f"cross-volume move planned: {source} -> {destination}")
        except AttributeError:
            pass

    return PreflightReport(
        ready_count=len(ready),
        blocked_count=len(blocked),
        total_bytes=total_bytes,
        file_renames=file_renames,
        directories_created=directories_created,
        directories_renamed=directories_renamed,
        identities=tuple(identities),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def verify_completed_rename(
    preflight: PreflightReport,
    completed: list[tuple[Path, Path]],
) -> VerificationReport:
    identities = {str(source.resolve()).casefold(): identity for source, identity in preflight.identities}
    issues: list[VerificationIssue] = []
    verified = 0

    for old_path, new_path in completed:
        old_resolved = Path(old_path).resolve()
        new_resolved = Path(new_path).resolve()
        identity = identities.get(str(old_resolved).casefold())
        if identity is None:
            issues.append(VerificationIssue(old_resolved, new_resolved, "preflight identity missing"))
            continue
        if old_resolved.exists() and str(old_resolved).casefold() != str(new_resolved).casefold():
            issues.append(VerificationIssue(old_resolved, new_resolved, "original path still exists after rename"))
            continue
        if not new_resolved.exists() or not new_resolved.is_file():
            issues.append(VerificationIssue(old_resolved, new_resolved, "destination file is missing"))
            continue

        matches, detail = _identity_matches(new_resolved, identity)
        if not matches:
            issues.append(VerificationIssue(old_resolved, new_resolved, detail))
            continue
        verified += 1

    if len(completed) != preflight.ready_count:
        issues.append(
            VerificationIssue(
                Path("."),
                Path("."),
                f"completed count {len(completed)} does not match preflight READY count {preflight.ready_count}",
            )
        )

    return VerificationReport(
        checked_count=len(completed),
        verified_count=verified,
        issues=tuple(issues),
    )
