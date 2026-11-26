"""Persist/display OCR evidence without consulting current configuration."""

LABELS = {
    "done": "Выполнен", "empty": "Текст не найден",
    "not_required": "Не требуется", "skipped": "Пропущен",
    "error": "Ошибка", "pending": "Ожидает", "unknown": "Нет данных",
}
ENGINES = {"rapidocr": "RapidOCR", "paddleocr": "PaddleOCR", "surya": "Surya"}


def pages(details):
    records = details.get("ocr", [])
    return [p for p in records if isinstance(p, dict)] if isinstance(records, list) else []


def evidence(details, status, *, required=None, enabled=None, attempted=False):
    details = details if isinstance(details, dict) else {}
    records = pages(details)
    engines = sorted({p.get("engine") or p.get("backend") for p in records
                      if isinstance(p.get("engine") or p.get("backend"), str)
                      and (p.get("engine") or p.get("backend"))})
    if (attempted or records) and status in {"FAILED", "ENCRYPTED", "UNSUPPORTED"}:
        state = "error"
    elif records:
        state = "done" if any(str(b.get("text", "")).strip()
                              for p in records for b in (p.get("blocks") or [])
                              if isinstance(b, dict)) else "empty"
    elif attempted:
        state = "unknown"
    elif required and enabled is False:
        state = "skipped"
    elif required and enabled is True:
        state = "pending"
    elif required is False and status == "ANALYZED":
        state = "not_required"
    else:
        state = "unknown"
    return {"ocr_state": state, "ocr_engines": engines}


def display(details, status):
    details = details if isinstance(details, dict) else {}
    meta = details if details.get("ocr_state") in LABELS else evidence(details, status)
    state = meta["ocr_state"]
    saved_engines = meta.get("ocr_engines", [])
    engines = ", ".join(ENGINES.get(e, e) for e in saved_engines if isinstance(e, str)) if isinstance(saved_engines, list) else ""
    return LABELS[state], engines or ("Нет данных" if state in {"done", "empty", "error", "unknown"} else "—")
