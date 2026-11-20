import pytest

from app.snils import snils_valid, snils_matches, normalize_snils
from app.advanced_detectors import pii
from app.document_templates import match_document, template_config


@pytest.mark.parametrize("number", ["112-233-445 95", "112233445-95", "112 233 445 95", "112–233—445-95", "11223344595"])
def test_valid_formats(number):
    assert normalize_snils(number) == "11223344595"
    assert snils_valid(number)
    assert snils_matches(number)[0]["verification"] == "confirmed"


def test_invalid_needs_context_and_lower_confidence():
    assert not snils_matches("Заказ 112233445-96")
    match = snils_matches("СНИЛС сотрудника 112233445-96")[0]
    assert not match["checksum_valid"]
    assert match["verification"] == "suspected"
    assert match["confidence"] < snils_matches("11223344595")[0]["confidence"]
    result = match_document("СНИЛС 112233445-96", template_config("snils_ru"))
    assert result["verification"] == "suspected"
    assert "неверная" in result["reason"]


@pytest.mark.parametrize("text", ["СНИЛС 00000000000", "000-000-000 00", "1112233445959", "112233445-96", "СНИЛС\n\nЗаказ 11223344596"])
def test_negative_numbers(text):
    assert not snils_matches(text)


def test_checksum_boundaries():
    for number in ("03164104100", "20018713000", "32662878100", "76084018400"):
        assert snils_valid(number)
    assert snils_valid("10000000009")
    assert snils_valid("00000000101")
    assert not snils_valid("11223344596")
    assert not snils_valid("112233445AA")


def test_reported_compact_format():
    assert snils_matches("СНИЛС 100080947-00")[0]["verification"] == "suspected"


def test_pii_preserves_verification():
    hits = [f for f in pii("СНИЛС 112233445-96") if f["category"] == "RU_SNILS"]
    assert len(hits) == 1 and hits[0]["risk"] == 40
    assert hits[0]["verification"] == "suspected"