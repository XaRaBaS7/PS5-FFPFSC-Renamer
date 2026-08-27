from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import (
    COMPONENT_TITLE,
    COMPONENT_TITLE_ID,
    COMPONENT_VERSION,
    FOLDER_ALWAYS_NEW,
    FOLDER_FILE_ONLY,
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    FOLDER_SMART,
    NamingOptions,
    build_output_stem,
    compact_ps5_version,
    example_output,
    normalize_folder_handling,
    sanitize_windows_component,
)


def test_compact_ps5_version() -> None:
    assert compact_ps5_version("01.000.000") == "1.0"
    assert compact_ps5_version("02.500.000") == "2.5"
    assert compact_ps5_version("01.250.000") == "1.25"
    assert compact_ps5_version("01.005.000") == "1.005"
    assert compact_ps5_version("01.000.001") == "1.0.1"


def _returnal() -> GameMetadata:
    return GameMetadata(
        "PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )


def test_build_full_output_name() -> None:
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        compact_version=True,
        version_prefix=True,
    )
    assert build_output_stem(_returnal(), options) == "PPSA01285 - Returnal - v1.0"


def test_title_can_come_before_ppsa() -> None:
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        component_order=(COMPONENT_TITLE, COMPONENT_TITLE_ID, COMPONENT_VERSION),
    )
    assert build_output_stem(_returnal(), options) == "Returnal - PPSA01285 - v1.0"


def test_version_can_come_first() -> None:
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        component_order=(COMPONENT_VERSION, COMPONENT_TITLE, COMPONENT_TITLE_ID),
    )
    assert build_output_stem(_returnal(), options) == "v1.0 - Returnal - PPSA01285"


def test_original_version_format() -> None:
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        compact_version=False,
        version_prefix=False,
    )
    assert build_output_stem(_returnal(), options) == "PPSA01285 - Returnal - 01.000.000"


def test_invalid_windows_title_characters_are_sanitized() -> None:
    assert sanitize_windows_component('Ratchet: Rift / Apart?') == "Ratchet Rift Apart"


def test_one_folder_per_game_preview() -> None:
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        folder_handling=FOLDER_ONE_PER_GAME,
    )
    assert example_output(options) == (
        "PPSA01285 - Returnal - v1.0\\"
        "PPSA01285 - Returnal - v1.0.ffpfsc"
    )


def test_flat_and_keep_structure_previews_are_file_only() -> None:
    for mode in (FOLDER_ROOT_FLAT, FOLDER_KEEP_STRUCTURE):
        options = NamingOptions(
            include_title_id=True,
            include_title=True,
            include_version=True,
            folder_handling=mode,
        )
        assert example_output(options) == "PPSA01285 - Returnal - v1.0.ffpfsc"


def test_legacy_folder_modes_normalize_safely() -> None:
    assert normalize_folder_handling(FOLDER_FILE_ONLY) == FOLDER_KEEP_STRUCTURE
    assert normalize_folder_handling(FOLDER_FILE_ONLY, create_folder=True) == FOLDER_ONE_PER_GAME
    assert normalize_folder_handling(FOLDER_SMART) == FOLDER_ONE_PER_GAME
    assert normalize_folder_handling(FOLDER_ALWAYS_NEW) == FOLDER_ONE_PER_GAME
