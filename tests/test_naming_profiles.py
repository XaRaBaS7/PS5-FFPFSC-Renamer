from __future__ import annotations

import json

from ps5_ffpfsc_renamer.naming import (
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    FOLDER_FILE_ONLY,
)
from ps5_ffpfsc_renamer.naming_profiles import (
    BUNDLED_PROFILES,
    NamingProfile,
    all_profiles,
    delete_user_profile,
    load_user_profiles,
    save_user_profiles,
    upsert_user_profile,
)


def test_user_profiles_round_trip(tmp_path):
    path = tmp_path / "profiles.json"
    profile = NamingProfile(
        name="My archive",
        include_title_id=True,
        include_title=True,
        include_version=True,
        compact_version=False,
        version_prefix=False,
        folder_handling=FOLDER_FILE_ONLY,
        component_order=(COMPONENT_TITLE, COMPONENT_VERSION, COMPONENT_TITLE_ID),
        separator="__",
    )

    save_user_profiles([profile], path)
    loaded = load_user_profiles(path)

    assert loaded == [profile]


def test_upsert_replaces_case_insensitive_name(tmp_path):
    path = tmp_path / "profiles.json"
    upsert_user_profile(NamingProfile(name="Archive", include_title=True), path)
    upsert_user_profile(NamingProfile(name="archive", include_version=True), path)

    loaded = load_user_profiles(path)
    assert len(loaded) == 1
    assert loaded[0].include_version is True


def test_delete_profile(tmp_path):
    path = tmp_path / "profiles.json"
    save_user_profiles([NamingProfile(name="One"), NamingProfile(name="Two")], path)

    assert delete_user_profile("one", path) is True
    assert [profile.name for profile in load_user_profiles(path)] == ["Two"]
    assert delete_user_profile("missing", path) is False


def test_invalid_profile_file_is_safe(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{bad-json", encoding="utf-8")
    assert load_user_profiles(path) == []


def test_invalid_separator_falls_back(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "profiles": [
                    {
                        "name": "Unsafe",
                        "separator": "/",
                        "component_order": ["title", "title_id", "version"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_user_profiles(path)
    assert loaded[0].separator == " - "


def test_all_profiles_exposes_bundled_then_user(tmp_path):
    path = tmp_path / "profiles.json"
    save_user_profiles([NamingProfile(name="Personal")], path)
    profiles = all_profiles(path)

    assert [profile.name for profile, built_in in profiles[: len(BUNDLED_PROFILES)]] == [
        profile.name for profile in BUNDLED_PROFILES
    ]
    assert all(built_in for _profile, built_in in profiles[: len(BUNDLED_PROFILES)])
    assert profiles[-1][0].name == "Personal"
    assert profiles[-1][1] is False
