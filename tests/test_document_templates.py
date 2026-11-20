"""Type-template regression: variable personal values must never be template constants."""
from app.document_templates import match_document, template_config, finding_for_template

def test_passport_any_valid_person_not_just_uploaded_sample():
    template = template_config("passport_ru")
    a = "РОССИЙСКАЯ ФЕДЕРАЦИЯ ПАСПОРТ ФАМИЛИЯ ИВАНОВА ИМЯ МАРИЯ ДАТА ВЫДАЧИ 10.10.2010 КОД ПОДРАЗДЕЛЕНИЯ 770-001"
    b = "РОССИЙСКАЯ ФЕДЕРАЦИЯ ПАСПОРТ ФАМИЛИЯ ПЕТРОВА ИМЯ АННА МЕСТО РОЖДЕНИЯ МОСКВА 12 34 987654"
    for doc in (a, b):
        result = match_document(doc, template)
        assert result and result["category"] == "RU_PASSPORT"
        assert "ИВАНОВА" not in str(result) and "ПЕТРОВА" not in str(result)
    assert "иванова" not in str(template)

def test_not_triggered_by_bare_number_or_general_discussion():
    template = template_config("passport_ru")
    assert not match_document("1234 567890", template)
    assert not match_document("Обсуждали российский паспорт, фамилию и имя, без реквизитов", template)
    assert not match_document("Дата выдачи 12.03.2022", template)

def test_snils_valid_checksum_and_anchor():
    from app.advanced_detectors import snils_valid
    from app.document_templates import match_document
    number = next(f"{n:09d}{c:02d}" for n in range(100000000, 100000500)
                  for c in range(100) if snils_valid(f"{n:09d}{c:02d}"))
    formatted = f"{number[:3]}-{number[3:6]}-{number[6:9]} {number[9:]}"
    assert match_document("СНИЛС " + formatted, template_config("snils_ru"))
    assert not match_document("СНИЛС 123-456-789 00", template_config("snils_ru"))

def test_inn_requires_checksum_and_fixed_context():
    from app.detectors import inn_valid
    from app.document_templates import match_document
    number = next(str(n) for n in range(7700000000, 7700005000) if inn_valid(str(n)))
    assert match_document("ИНН " + number, template_config("inn_ru"))
    assert not match_document(number, template_config("inn_ru"))

def test_evidence_does_not_expose_personal_data():
    data = "ПАСПОРТ РОССИЙСКАЯ ФЕДЕРАЦИЯ ФАМИЛИЯ СЕКРЕТНОВА ДАТА ВЫДАЧИ 12.03.2021"
    hit = finding_for_template(data, template_config("passport_ru"), "ref-1", "scan.png")
    assert hit
    assert "СЕКРЕТНОВА" not in str(hit) and "12.03.2021" not in str(hit)
    assert hit["rule_id"] == "document-template:ref-1"


def test_anchor_must_match_whole_words():
    from app.detectors import inn_valid

    number = next(str(n) for n in range(7700000000, 7700005000) if inn_valid(str(n)))
    assert not match_document("Длинный номер " + number, template_config("inn_ru"))
    assert match_document("ИНН: " + number, template_config("inn_ru"))


def test_template_config_does_not_share_mutable_anchors():
    config = template_config("inn_ru")
    config["anchors"].append("personal sample")
    assert "personal sample" not in template_config("inn_ru")["anchors"]
