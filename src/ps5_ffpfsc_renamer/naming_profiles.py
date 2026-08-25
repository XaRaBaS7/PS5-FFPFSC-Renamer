from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .naming import (
    COMPONENTS,
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    FOLDER_ALWAYS_NEW,
    FOLDER_FILE_ONLY,
    FOLDER_HANDLING_MODES,
    FOLDER_SMART,
)

_PROFILE_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class NamingProfile:
    name: str
    include_title_id: bool = True
    include_title: bool = False
    include_version: bool = False
    compact_version: bool = True
    version_prefix: bool = True
    folder_handling: str = FOLDER_SMART
    component_order: tuple[str, ...] = COMPONENTS
    separator: str = " - "


BUNDLED_PROFILES: tuple[NamingProfile, ...] = (
    NamingProfile(
        name="ShadowMount / PPSA only",
        include_title_id=True,
        include_title=False,
        include_version=False,
        folder_handling=FOLDER_SMART,
        component_order=(COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
    ),
    NamingProfile(
        name="PPSA + Title",
        include_title_id=True,
        include_title=True,
        include_version=False,
        folder_handling=FOLDER_SMART,
        component_order=(COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
    ),
    NamingProfile(
        name="Title + PPSA",
        include_title_id=True,
        include_title=True,
        include_version=False,
        folder_handling=FOLDER_SMART,
        component_order=(COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION),
    ),
    NamingProfile(
        name="Full archive",
        include_title_id=True,
        include_title=True,
        include_version=True,
        compact_version=True,
        version_prefix=True,
        folder_handling=FOLDER_SMART,
        component_order=(COMPONENT_TITLE_ID, COMPONENT_TITLE, COMPONENT_VERSION),
    ),
    NamingProfile(
        name="Title + Version + PPSA",
        include_title_id=True,
        include_title=True,
        include_version=True,
        compact_version=True,
        version_prefix=True,
        folder_handling=FOLDER_SMART,
        component_order=(COMPONENT_TITLE, COMPONENT_VERSION, COMPONENT_TITLE_ID),
    ),
)


def default_profiles_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "PS5-FFPFSC-Renamer" if base else Path.home() / ".ps5-ffpfsc-renamer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "naming-profiles.json"


def _safe_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if not text:
        return None
    return text[:80]


def _safe_order(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return COMPONENTS
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item in COMPONENTS and item not in result:
            result.append(item)
    for component in COMPONENTS:
        if component not in result:
            result.append(component)
    return tuple(result)


def _safe_folder(value: object) -> str:
    return value if isinstance(value, str) and value in FOLDER_HANDLING_MODES else FOLDER_SMART


def _safe_separator(value: object) -> str:
    if not isinstance(value, str):
        return " - "
    # A separator belongs between already-sanitized filename components. Keep
    # it short and refuse Windows path separators / reserved filename chars.
    text = value[:12]
    if any(char in text for char in '<>:"/\\|?*\x00'):
        return " - "
    return text


def _from_dict(data: object) -> NamingProfile | None:
    if not isinstance(data, dict):
        return None
    name = _safe_name(data.get("name"))
    if name is None:
        return None
    return NamingProfile(
        name=name,
        include_title_id=data.get("include_title_id") if isinstance(data.get("include_title_id"), bool) else True,
        include_title=data.get("include_title") if isinstance(data.get("include_title"), bool) else False,
        include_version=data.get("include_version") if isinstance(data.get("include_version"), bool) else False,
        compact_version=data.get("compact_version") if isinstance(data.get("compact_version"), bool) else True,
        version_prefix=data.get("version_prefix") if isinstance(data.get("version_prefix"), bool) else True,
        folder_handling=_safe_folder(data.get("folder_handling")),
        component_order=_safe_order(data.get("component_order")),
        separator=_safe_separator(data.get("separator")),
    )


def load_user_profiles(path: Path | None = None) -> list[NamingProfile]:
    target = path or default_profiles_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict) or payload.get("schema") != _PROFILE_SCHEMA:
        return []
    raw = payload.get("profiles")
    if not isinstance(raw, list):
        return []
    result: list[NamingProfile] = []
    seen: set[str] = set()
    for item in raw:
        profile = _from_dict(item)
        if profile is None:
            continue
        key = profile.name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(profile)
    return result


def save_user_profiles(profiles: Iterable[NamingProfile], path: Path | None = None) -> Path:
    target = path or default_profiles_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized: list[NamingProfile] = []
    seen: set[str] = set()
    for profile in profiles:
        name = _safe_name(profile.name)
        if name is None:
            continue
        candidate = NamingProfile(
            name=name,
            include_title_id=bool(profile.include_title_id),
            include_title=bool(profile.include_title),
            include_version=bool(profile.include_version),
            compact_version=bool(profile.compact_version),
            version_prefix=bool(profile.version_prefix),
            folder_handling=_safe_folder(profile.folder_handling),
            component_order=_safe_order(list(profile.component_order)),
            separator=_safe_separator(profile.separator),
        )
        key = candidate.name.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(candidate)

    payload = {
        "schema": _PROFILE_SCHEMA,
        "profiles": [
            {
                **asdict(profile),
                "component_order": list(profile.component_order),
            }
            for profile in normalized
        ],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def upsert_user_profile(profile: NamingProfile, path: Path | None = None) -> Path:
    profiles = load_user_profiles(path)
    key = profile.name.casefold()
    replaced = False
    for index, existing in enumerate(profiles):
        if existing.name.casefold() == key:
            profiles[index] = profile
            replaced = True
            break
    if not replaced:
        profiles.append(profile)
    return save_user_profiles(profiles, path)


def delete_user_profile(name: str, path: Path | None = None) -> bool:
    profiles = load_user_profiles(path)
    key = name.casefold()
    kept = [profile for profile in profiles if profile.name.casefold() != key]
    if len(kept) == len(profiles):
        return False
    save_user_profiles(kept, path)
    return True


def all_profiles(path: Path | None = None) -> list[tuple[NamingProfile, bool]]:
    """Return (profile, built_in) pairs with bundled profiles first."""
    bundled_names = {profile.name.casefold() for profile in BUNDLED_PROFILES}
    result: list[tuple[NamingProfile, bool]] = [(profile, True) for profile in BUNDLED_PROFILES]
    result.extend(
        (profile, False)
        for profile in load_user_profiles(path)
        if profile.name.casefold() not in bundled_names
    )
    return result
