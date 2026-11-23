from app.text_normalizer import DEFAULTS, normalize


def test_original_is_never_modified():
    source = "Завтра б0мба\u200b в офисе"
    recovered, markers = normalize(source)
    assert source == "Завтра б0мба\u200b в офисе"
    assert recovered == "Завтра бомба в офисе"
    assert "invisible_characters" in markers
    assert "mixed_script_or_digits" in markers


def test_mixed_alphabets_and_high_sensitivity():
    restored, changes = normalize("В офисе бoмба", "medium")
    assert restored == "В офисе бомба"
    assert "mixed_script_or_digits" in changes
    assert normalize("б-о-м-б-а", "high")[0] == "бомба"
    assert normalize("б-о-м-б-а", "low")[0] == "б-о-м-б-а"


def test_ordinary_english_not_transliterated():
    assert normalize("office payment", "high")[0] == "office payment"
    assert normalize("б0мба", "low")[0] == "б0мба"


def test_unknown_sensitivity_rejected():
    import pytest
    with pytest.raises(ValueError):
        normalize("текст", "unsafe")


def test_feature_disabled_by_default():
    assert DEFAULTS["enabled"] is False
    assert DEFAULTS["mode"] == "detect"
