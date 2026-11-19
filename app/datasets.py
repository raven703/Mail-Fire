"""Bounded CSV/JSONL labeling imports. Never trust external LLM labels as ground truth."""

import csv
import io
import json

MAX_ROWS = 5000
MAX_TEXT = 100000


def parse_dataset(raw, filename, category_map):
    if not filename.lower().endswith((".csv", ".jsonl")):
        raise ValueError("Допустимы только .csv или .jsonl")
    try:
        data = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Требуется кодировка UTF-8") from exc
    if filename.lower().endswith(".jsonl"):

        def source():
            for line_no, line in enumerate(io.StringIO(data), 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Некорректный JSONL, строка {line_no}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"Строка {line_no}: ожидается JSON-объект")
                yield value

        rows = source()
    else:
        rows = csv.DictReader(io.StringIO(data))
        if not rows.fieldnames or not {"text", "labels"}.issubset(set(rows.fieldnames)):
            raise ValueError("CSV должен содержать столбцы text и labels")
    accepted = []
    seen = {}
    for number, row in enumerate(rows, 1):
        if number > MAX_ROWS:
            raise ValueError("Максимум 5000 строк в одном импорте")
        value = row.get("text", "")
        if not isinstance(value, str) or not 10 <= len(value.strip()) <= MAX_TEXT:
            raise ValueError(f"Строка {number}: текст должен содержать 10–100000 символов")
        source_labels = row.get("labels", [])
        if isinstance(source_labels, str):
            source_labels = [x.strip() for x in source_labels.replace("|", ";").split(";") if x.strip()]
        if not isinstance(source_labels, list) or any(not isinstance(x, str) for x in source_labels):
            raise ValueError(f"Строка {number}: labels должен быть списком или строкой через ;")
        if len(source_labels) > 20:
            raise ValueError(f"Строка {number}: максимум 20 категорий")
        unknown = [x for x in source_labels if x not in category_map]
        if unknown:
            raise ValueError(f"Строка {number}: неизвестные метки: {', '.join(unknown[:3])}")
        labels = sorted({category_map[x] for x in source_labels}) or ["NORMAL"]
        if "NORMAL" in labels and len(labels) != 1:
            raise ValueError(f"Строка {number}: NORMAL не сочетается с другими метками")
        normalized = " ".join(value.strip().lower().split())
        if normalized in seen:
            if seen[normalized] != labels:
                raise ValueError(f"Строка {number}: противоречивая разметка одинакового текста")
            continue
        seen[normalized] = labels
        accepted.append({"text": value.strip(), "labels": labels})
    if not accepted:
        raise ValueError("Не найдено подходящих примеров")
    return accepted
