import pytest

from ps5_ffpfsc_renamer.metadata import metadata_from_param_json, normalize_title_id


def test_normalize_title_id() -> None:
    assert normalize_title_id(" ppsa01285 ") == "PPSA01285"
    assert normalize_title_id("PPSA1234") is None
    assert normalize_title_id("PPSAABCDE") is None


def test_metadata_uses_default_language() -> None:
    metadata = metadata_from_param_json(
        {
            "titleId": "PPSA01285",
            "contentVersion": "01.000.000",
            "masterVersion": "01.00",
            "localizedParameters": {
                "defaultLanguage": "en-US",
                "en-US": {"titleName": "Example Game"},
            },
        }
    )
    assert metadata.title_id == "PPSA01285"
    assert metadata.title_name == "Example Game"
    assert metadata.content_version == "01.000.000"
    assert metadata.is_ppsa is True


def test_missing_title_id_fails() -> None:
    with pytest.raises(ValueError):
        metadata_from_param_json({})
