"""Type-based document recognition: fixed layout labels + validated variable fields.

Never copy person's name, number or other individual details from a sample into
the template. Recognition is local, OCR-dependent and deliberately conservative.
"""
import re
from app.detectors import inn_valid
from app.advanced_detectors import snils_valid

TEMPLATES = {
    "passport_ru": {
        "label": "Паспорт гражданина РФ",
        "category": "RU_PASSPORT",
        "anchors": [
            "российская федерация", "паспорт", "дата выдачи",
            "код подразделения", "место рождения", "фамилия",
            "отчество", "личный код",
        ],
        "min_anchors": 3,
    },
    "snils_ru": {
        "label": "СНИЛС / страховое свидетельство",
        "category": "RU_SNILS",
        "anchors": [
            "страховое свидетельство", "обязательного пенсионного страхования",
            "страховой номер", "индивидуального лицевого счета", "снилс",
        ],
        "min_anchors": 1,
    },
    "inn_ru": {
        "label": "Свидетельство ИНН",
        "category": "RU_INN",
        "anchors": [
            "идентификационный номер налогоплательщика",
            "свидетельство о постановке на учет",
            "федеральная налоговая служба", "налоговом органе", "инн",
        ],
        "min_anchors": 1,
    },
}

def normalized(value):
    return re.sub(r"\s+", " ", re.sub(r"[^а-яa-z0-9]+", " ", value.casefold().replace("ё", "е"))).strip()

def template_config(kind):
    if kind not in TEMPLATES:
        raise ValueError("Неизвестный тип шаблона")
    spec = TEMPLATES[kind]
    # Only allowlisted fixed words are persisted, never OCR values from sample.
    return {"kind": kind, "version": 1, "anchors": list(spec["anchors"]),
            "min_anchors": spec["min_anchors"], "category": spec["category"]}

def _variable_present(text, kind):
    if kind == "passport_ru":
        from app.passport import passport_spans

        if passport_spans(text):
            return True
        # Typical series+number, subdivision code or issue-date evidence.
        series = re.search(r"(?<!\d)\d{2}\s?\d{2}\s?\d{6}(?!\d)", text)
        subdivision = re.search(r"(?<!\d)\d{3}[- ]\d{3}(?!\d)", text)
        issued = re.search(r"(?<!\d)\d{2}[./]\d{2}[./]\d{4}(?!\d)", text)
        return bool(series or subdivision or issued)
    if kind == "snils_ru":
        return any(snils_valid(m.group()) for m in re.finditer(
            r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{3}[ -]?\d{2}(?!\d)", text))
    if kind == "inn_ru":
        return any(inn_valid(m.group()) for m in re.finditer(
            r"(?<!\d)(?:\d{12}|\d{10})(?!\d)", text))
    return False

def match_document(text, template):
    """Return matched fixed labels only; do not expose personal values in evidence."""
    if not isinstance(template, dict) or template.get("kind") not in TEMPLATES:
        return None
    kind = template["kind"]
    spec = TEMPLATES[kind]
    document = normalized(text)
    # Enforce built-in anchors, even if a stored template was tampered with.
    anchors = [
        a for a in spec["anchors"]
        if re.search(r"(?<!\w)" + re.escape(normalized(a)) + r"(?!\w)", document)
    ]
    from app.passport import passport_spans

    passport_fields = kind == "passport_ru" and bool(passport_spans(text))
    if not passport_fields and (len(anchors) < spec["min_anchors"] or not _variable_present(text, kind)):
        return None
    confidence = min(0.98, 0.60 + 0.08 * len(anchors))
    return {"category": spec["category"], "kind": kind,
            "confidence": round(confidence, 2), "anchors": anchors,
            "reason": "Тип документа: постоянные реквизиты бланка и формат переменного поля"}

def finding_for_template(text, template, reference_id, filename):
    matched = match_document(text, template)
    if not matched:
        return None
    return {"category": matched["category"], "source": "document-template",
            "rule_id": "document-template:" + reference_id,
            "risk": 75, "confidence": matched["confidence"],
            "start": 0, "end": 0,
            "excerpt": "; ".join(matched["anchors"])[:300],
            "reason": matched["reason"], "status": "ANALYZED",
            "version": "document-template-1", "filename": filename}
