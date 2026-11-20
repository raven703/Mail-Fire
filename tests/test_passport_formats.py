import pytest

from app.passport import passport_spans
from app.advanced_detectors import pii
from app.document_templates import match_document, template_config


@pytest.mark.parametrize("text", [
    "Паспорт РФ: 62 17 864209",
    "Паспорт: серия 6217, номер 864209",
    "Паспорт гражданина РФ; серия: 62-17; № 864209",
    "Паспорт РФ | Серия | Номер\n6217 | 864209",
    "Российская Федерация. Паспорт. Фамилия Тестов. Серия 62 17, номер 864209",
    "Паспорт РФ 6217/864209",
])
def test_contextual_passport_formats(text):
    assert passport_spans(text)
    assert any(f["category"] == "RU_PASSPORT" for f in pii(text))


@pytest.mark.parametrize("text", [
    "Номер заказа 6217864209",
    "Серия 6217 номер 864209 — товарная накладная",
    "Паспорт проекта. Бюджет 62178642090 рублей",
    "Паспорт проекта 6217864209",
    "Тестовый паспорт: серия 0000, номер 000000",
    "Обсуждение паспорта без реквизитов",
    "Паспорт РФ\n\nНомер заказа 6217864209",
])
def test_random_numbers_and_discussions_are_not_passports(text):
    assert not passport_spans(text)


def test_template_uses_labeled_fields_without_retaining_values():
    result = match_document(
        "Паспорт РФ. Фамилия Тестов. Код подразделения 123-456. Серия 62 17, номер 864209",
        template_config("passport_ru"),
    )
    assert result and result["category"] == "RU_PASSPORT"
    assert "864209" not in str(result)
    assert match_document("Паспорт РФ: серия 6217, номер 864209", template_config("passport_ru"))