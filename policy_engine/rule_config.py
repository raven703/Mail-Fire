"""Native validation of the original category rule configuration contract."""

from app.categories import safe_regex


def validate_config(kind, config):
    if kind == 'horizon':
        from app.horizon import validate
        return validate(config)
    def phrases(key):
        items = config.get(key, [])
        if not isinstance(items, list) or len(items) > 30 or any(
            not isinstance(value, str) or not 3 <= len(value.strip()) <= 120 for value in items
        ):
            raise ValueError("Фразы: 3–120 символов, не более 30")
        return sorted({value.strip() for value in items})

    def number(key, default, low, high, integer=False):
        value = config.get(key, default)
        if type(value) not in ({int} if integer else {int, float}) or not low <= value <= high:
            raise ValueError("Некорректное значение " + key)
        return value

    excludes = phrases("exclude_phrases")
    if kind == "regex":
        pattern = config.get("pattern", "")
        if not isinstance(pattern, str):
            raise ValueError("Ожидается строка Regex")
        safe_regex(pattern)
        return {"pattern": pattern, "exclude_phrases": excludes}
    if kind == "reference":
        ids = config.get("reference_ids", [])
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("Выберите уникальные эталоны (1–20)")
        return {"reference_ids": sorted(ids), "min_similarity": number("min_similarity", 0.8, 0.5, 1), "exclude_phrases": excludes}
    if kind == "ml":
        return {"min_confidence": number("min_confidence", 0.7, 0, 1), "exclude_phrases": excludes}
    if kind != "keywords":
        raise ValueError("Неизвестный тип правила")
    mode = config.get("match_type", "substring")
    if mode not in {"substring", "word", "morphology", "flexible"}:
        raise ValueError("Неизвестный режим сопоставления")
    values = phrases("phrases")
    terms = config.get("terms", [])
    if not isinstance(terms, list) or len(terms) > 30:
        raise ValueError("Не более 30 терминов")
    normalized = []
    if mode == "flexible":
        for item in terms:
            if not isinstance(item, dict) or set(item) - {"text", "weight", "required"}:
                raise ValueError("Некорректные поля термина")
            text, weight, required = item.get("text"), item.get("weight", 1), item.get("required", False)
            if not isinstance(text, str) or not 2 <= len(text.strip()) <= 120:
                raise ValueError("Длина термина: 2–120")
            if type(weight) is not int or not 1 <= weight <= 100 or type(required) is not bool:
                raise ValueError("Некорректные вес/required")
            normalized.append({"text": text.strip(), "weight": weight, "required": required})
        if not normalized:
            raise ValueError("Добавьте взвешенный термин")
    elif not values:
        raise ValueError("Добавьте ключевые фразы")
    ordered = config.get("ordered", False)
    if type(ordered) is not bool:
        raise ValueError("ordered должен быть логическим")
    return {
        "phrases": values, "match_type": mode, "terms": normalized, "exclude_phrases": excludes,
        "min_score": number("min_score", 1, 1, 1000, True),
        "window": number("window", 12, 1, 80, True), "ordered": ordered,
    }