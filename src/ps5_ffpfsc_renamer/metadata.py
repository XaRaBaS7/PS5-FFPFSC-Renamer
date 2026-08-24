from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_TITLE_ID_RE = re.compile(r"^[A-Z]{4}[0-9]{5}$")
_PPSA_RE = re.compile(r"^PPSA[0-9]{5}$")


@dataclass(frozen=True, slots=True)
class GameMetadata:
    title_id: str
    title_name: str | None = None
    content_version: str | None = None
    master_version: str | None = None

    @property
    def is_ppsa(self) -> bool:
        return bool(_PPSA_RE.fullmatch(self.title_id))


def normalize_title_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if not _TITLE_ID_RE.fullmatch(normalized):
        return None
    return normalized


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _title_name(data: dict[str, Any]) -> str | None:
    localized = data.get("localizedParameters")
    if not isinstance(localized, dict):
        return None

    default_language = localized.get("defaultLanguage")
    if isinstance(default_language, str):
        entry = localized.get(default_language)
        if isinstance(entry, dict):
            name = _optional_text(entry.get("titleName"))
            if name:
                return name

    for key, entry in localized.items():
        if key == "defaultLanguage" or not isinstance(entry, dict):
            continue
        name = _optional_text(entry.get("titleName"))
        if name:
            return name
    return None


def metadata_from_param_json(data: dict[str, Any]) -> GameMetadata:
    title_id = normalize_title_id(data.get("titleId") or data.get("title_id"))
    if title_id is None:
        raise ValueError("param.json does not contain a valid PS5 titleId")

    return GameMetadata(
        title_id=title_id,
        title_name=_title_name(data),
        content_version=_optional_text(data.get("contentVersion")),
        master_version=_optional_text(data.get("masterVersion")),
    )
