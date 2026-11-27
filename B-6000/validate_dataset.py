# -*- coding: utf-8 -*-
"""
Валидация корпуса B-6000.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

FIN_PLANS = "pack-ru2-financial-plans"
PRICING = "pack-ru2-pricing"
VALID_LABELS = {(), (FIN_PLANS,), (PRICING,), (FIN_PLANS, PRICING)}
OUT_DIR = Path(__file__).parent


def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def check_jsonl(records):
    errors = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            errors.append(f"Line {i}: not a dict")
            continue
        for key in ["id", "subject", "body", "labels"]:
            if key not in r:
                errors.append(f"Line {i}: missing key '{key}'")
        if not r.get("body", "").strip():
            errors.append(f"Line {i}: empty body")
        labels = tuple(sorted(r.get("labels", [])))
        if labels not in VALID_LABELS:
            errors.append(f"Line {i}: invalid labels {r.get('labels')}")
    return errors


def check_duplicates(records):
    exact = []
    seen = {}
    for r in records:
        key = (r["subject"], r["body"])
        if key in seen:
            exact.append((seen[key]["id"], r["id"]))
        else:
            seen[key] = r
    return exact


def char_ngrams(text, n=3):
    text = re.sub(r"\s+", "", text.lower())
    return set(text[i:i + n] for i in range(len(text) - n + 1))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_near_duplicates(records, threshold=0.85):
    """Поиск близких дубликатов внутри сценарных групп (блокировка по group_id)."""
    groups = defaultdict(list)
    for idx, r in enumerate(records):
        groups[r["group_id"]].append(idx)

    ngram_sets = {}
    for idx, r in enumerate(records):
        text = r["subject"] + " " + r["body"]
        ngram_sets[idx] = char_ngrams(text, 3)

    pairs = []
    for gid, indices in groups.items():
        if len(indices) < 2:
            continue
        for i_pos in range(len(indices)):
            for j_pos in range(i_pos + 1, len(indices)):
                i = indices[i_pos]
                j = indices[j_pos]
                sim = jaccard(ngram_sets[i], ngram_sets[j])
                if sim > threshold:
                    pairs.append({
                        "id1": records[i]["id"],
                        "id2": records[j]["id"],
                        "group1": records[i]["group_id"],
                        "group2": records[j]["group_id"],
                        "similarity": float(sim),
                    })
    return pairs


def main():
    records = load_jsonl(OUT_DIR / "dataset.jsonl")
    print(f"Загружено записей: {len(records)}")

    report = {}
    report["total_emails"] = len(records)

    jsonl_errors = check_jsonl(records)
    report["jsonl_errors"] = jsonl_errors
    print(f"Ошибок JSONL: {len(jsonl_errors)}")

    ids = [r["id"] for r in records]
    report["unique_ids"] = len(set(ids))
    report["duplicate_ids"] = len(ids) - len(set(ids))
    print(f"Уникальных ID: {report['unique_ids']}, дубликатов ID: {report['duplicate_ids']}")

    label_counts = Counter()
    for r in records:
        label_counts[tuple(sorted(r["labels"]))] += 1
    report["label_distribution"] = {str(k): v for k, v in label_counts.items()}
    print("Распределение меток:", dict(report["label_distribution"]))

    fin_count = sum(1 for r in records if FIN_PLANS in r["labels"])
    prc_count = sum(1 for r in records if PRICING in r["labels"])
    report["financial_plans_count"] = fin_count
    report["pricing_count"] = prc_count
    print(f"pack-ru2-financial-plans: {fin_count}, pack-ru2-pricing: {prc_count}")

    groups = Counter(r["group_id"] for r in records)
    report["unique_groups"] = len(groups)
    report["group_size_distribution"] = dict(Counter(groups.values()))
    max_group = max(groups.values())
    report["max_group_size"] = max_group
    print(f"Уникальных групп: {report['unique_groups']}, макс. размер группы: {max_group}")

    wc = [len(re.findall(r"\S+", r["subject"] + " " + r["body"])) for r in records]
    report["min_words"] = min(wc)
    report["max_words"] = max(wc)
    report["avg_words"] = sum(wc) / len(wc)
    length_bins = Counter()
    for w in wc:
        if w <= 30:
            length_bins["short"] += 1
        elif w <= 150:
            length_bins["medium"] += 1
        elif w <= 400:
            length_bins["long"] += 1
        else:
            length_bins["very_long"] += 1
    report["length_distribution"] = dict(length_bins)
    print(f"Длина (слова): мин={min(wc)},{max(wc)}, сред={report['avg_words']:.1f}")
    print(f"Распределение длины: {dict(length_bins)}")

    ind_counts = Counter(r["industry"] for r in records)
    report["industry_distribution"] = dict(ind_counts)
    print(f"Отраслей: {len(ind_counts)}")

    diff_counts = Counter(r["difficulty"] for r in records)
    report["difficulty_distribution"] = dict(diff_counts)
    print(f"Сложность: {dict(diff_counts)}")

    leak_terms = ["pack-ru2", "label_reason", "group_id", "scenario", "features", "difficulty", "b6000"]
    leak_count = 0
    for r in records:
        text = (r["subject"] + " " + r["body"]).lower()
        for term in leak_terms:
            if term.lower() in text:
                leak_count += 1
                break
    report["metadata_leak_count"] = leak_count
    print(f"Писем с утечкой метаданных в текст: {leak_count}")

    exact_dups = check_duplicates(records)
    report["exact_duplicates"] = len(exact_dups)
    print(f"Точных дубликатов: {len(exact_dups)}")

    near_dups = check_near_duplicates(records)
    report["near_duplicates"] = len(near_dups)
    print(f"Близких дубликатов (threshold=0.85): {len(near_dups)}")

    with open(OUT_DIR / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "duplicate_report.json", "w", encoding="utf-8") as f:
        json.dump(near_dups, f, ensure_ascii=False, indent=2)

    passed = (
        len(records) == 6000
        and len(jsonl_errors) == 0
        and report["unique_ids"] == 6000
        and fin_count == 1800
        and prc_count == 1800
        and report["unique_groups"] >= 1500
        and max_group <= 5
        and leak_count == 0
    )
    print("\n" + ("=" * 50))
    print("ВАЛИДАЦИЯ ПРОЙДЕНА" if passed else "ВАЛИДАЦИЯ НЕ ПРОЙДЕНА")
    print("=" * 50)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())