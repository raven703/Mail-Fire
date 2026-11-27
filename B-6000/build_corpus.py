# -*- coding: utf-8 -*-
"""
Сборка корпуса B-6000: генерация 6000 писем, сохранение JSONL/CSV.
"""

import csv
import json
import random
from collections import Counter
from pathlib import Path

from scenarios import (
    ALL_SCENARIOS, FINANCIAL_SCENARIOS, PRICING_SCENARIOS, BOTH_SCENARIOS,
    SAFE_NORMAL_SCENARIOS, SAFE_HARD_SCENARIOS,
    FIN_PLANS, PRICING, TARGET_DISTRIBUTION,
)
from generator import gen_body_for_scenario, word_count

random.seed(42)

OUT_DIR = Path(__file__).parent
EMAILS_PER_SCENARIO_MAX = 5


def build_schedule():
    """Возвращает список (scenario, count) для генерации."""
    schedule = []

    # Только финансовые планы: 1200 писем из 208 сценариев
    n_fin = len(FINANCIAL_SCENARIOS)
    target_fin = TARGET_DISTRIBUTION["only_financial"]
    base = target_fin // n_fin
    rem = target_fin % n_fin
    for i, s in enumerate(FINANCIAL_SCENARIOS):
        c = base + (1 if i < rem else 0)
        c = min(c, EMAILS_PER_SCENARIO_MAX)
        schedule.append((s, c))

    # Только цены: 1200 писем из 200 сценариев
    n_prc = len(PRICING_SCENARIOS)
    target_prc = TARGET_DISTRIBUTION["only_pricing"]
    base = target_prc // n_prc
    rem = target_prc % n_prc
    for i, s in enumerate(PRICING_SCENARIOS):
        c = base + (1 if i < rem else 0)
        c = min(c, EMAILS_PER_SCENARIO_MAX)
        schedule.append((s, c))

    # Обе категории: 600 писем из 150 сценариев
    n_both = len(BOTH_SCENARIOS)
    target_both = TARGET_DISTRIBUTION["both"]
    base = target_both // n_both
    rem = target_both % n_both
    for i, s in enumerate(BOTH_SCENARIOS):
        c = base + (1 if i < rem else 0)
        c = min(c, EMAILS_PER_SCENARIO_MAX)
        schedule.append((s, c))

    # Обычные безопасные: 1500 из 375
    n_safe = len(SAFE_NORMAL_SCENARIOS)
    target_safe = TARGET_DISTRIBUTION["safe_normal"]
    base = target_safe // n_safe
    rem = target_safe % n_safe
    for i, s in enumerate(SAFE_NORMAL_SCENARIOS):
        c = base + (1 if i < rem else 0)
        c = min(c, EMAILS_PER_SCENARIO_MAX)
        schedule.append((s, c))

    # Сложные безопасные: 1500 из 375
    n_hard = len(SAFE_HARD_SCENARIOS)
    target_hard = TARGET_DISTRIBUTION["safe_hard"]
    base = target_hard // n_hard
    rem = target_hard % n_hard
    for i, s in enumerate(SAFE_HARD_SCENARIOS):
        c = base + (1 if i < rem else 0)
        c = min(c, EMAILS_PER_SCENARIO_MAX)
        schedule.append((s, c))

    return schedule


def generate_corpus():
    schedule = build_schedule()
    total_planned = sum(c for _, c in schedule)
    print(f"Запланировано писем: {total_planned}")

    emails = []
    email_id = 1
    for scenario, count in schedule:
        for i in range(count):
            subject, body, features = gen_body_for_scenario(scenario, i)
            wc = word_count(subject + " " + body)

            if wc < 5:
                continue

            record = {
                "id": f"B6000-{email_id:06d}",
                "group_id": scenario.group_id,
                "subject": subject,
                "body": body,
                "labels": list(scenario.labels),
                "industry": scenario.industry,
                "scenario": scenario.scenario,
                "difficulty": scenario.difficulty,
                "features": features,
                "label_reason": scenario.description,
                "word_count": wc,
            }
            emails.append(record)
            email_id += 1

    random.shuffle(emails)
    print(f"Сгенерировано писем: {len(emails)}")
    return emails


def assign_target_lengths(emails):
    """Назначает целевую длину письма согласно целевому распределению."""
    n = len(emails)
    targets = []
    targets += ["short"] * int(n * 0.20)      # 20%
    targets += ["medium"] * int(n * 0.45)     # 45%
    targets += ["long"] * int(n * 0.25)       # 25%
    targets += ["very_long"] * (n - len(targets))  # остальное ~10%
    random.shuffle(targets)
    for e, t in zip(emails, targets):
        e["target_length"] = t
    return emails


def save_jsonl(emails, path):
    with open(path, "w", encoding="utf-8") as f:
        for e in emails:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def save_csv(emails, path):
    fields = ["id", "group_id", "subject", "body", "labels",
              "industry", "scenario", "difficulty", "features", "label_reason"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in emails:
            row = {k: e.get(k, "") for k in fields}
            if isinstance(row["labels"], list):
                row["labels"] = ",".join(row["labels"])
            if isinstance(row["features"], list):
                row["features"] = ",".join(row["features"])
            writer.writerow(row)


def save_scenarios(path):
    seen = {}
    for s in ALL_SCENARIOS:
        seen[s.group_id] = {
            "group_id": s.group_id,
            "labels": s.labels,
            "industry": s.industry,
            "scenario": s.scenario,
            "difficulty": s.difficulty,
            "features": s.features,
            "description": s.description,
            "target_length": s.target_length,
        }
    with open(path, "w", encoding="utf-8") as f:
        for gid in sorted(seen.keys()):
            f.write(json.dumps(seen[gid], ensure_ascii=False) + "\n")
    print(f"Сценариев сохранено: {len(seen)}")


def print_stats(emails):
    print("\n=== Статистика корпуса ===")
    print(f"Всего писем: {len(emails)}")

    label_counts = Counter()
    for e in emails:
        key = tuple(sorted(e["labels"]))
        label_counts[key] += 1
    print("Распределение по меткам:")
    for k, v in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {list(k)}: {v}")

    print("\nРаспределение по отраслям:")
    ind_counts = Counter(e["industry"] for e in emails)
    for ind, c in sorted(ind_counts.items()):
        print(f"  {ind}: {c}")

    print("\nРаспределение по сложности:")
    diff_counts = Counter(e["difficulty"] for e in emails)
    for d, c in sorted(diff_counts.items()):
        print(f"  {d}: {c}")

    print("\nРаспределение по длине (слов):")
    wc_bins = Counter()
    for e in emails:
        wc = e["word_count"]
        if wc <= 30:
            wc_bins["short (<=30)"] += 1
        elif wc <= 150:
            wc_bins["medium (31-150)"] += 1
        elif wc <= 400:
            wc_bins["long (151-400)"] += 1
        else:
            wc_bins["very_long (>400)"] += 1
    for k, v in sorted(wc_bins.items()):
        print(f"  {k}: {v}")

    print("\nРаспределение по scenарным группам:")
    group_sizes = Counter(e["group_id"] for e in emails)
    sizes = Counter(group_sizes.values())
    for sz, cnt in sorted(sizes.items()):
        print(f"  групп размером {sz}: {cnt}")
    print(f"  Уникальных групп: {len(group_sizes)}")

    ids = [e["id"] for e in emails]
    print(f"\nУникальных ID: {len(set(ids))} из {len(ids)}")

    valid_labels = {(), (FIN_PLANS,), (PRICING,), (FIN_PLANS, PRICING)}
    bad = 0
    for e in emails:
        if tuple(sorted(e["labels"])) not in valid_labels:
            bad += 1
    print(f"Писем с некорректными метками: {bad}")


if __name__ == "__main__":
    emails = generate_corpus()
    emails = assign_target_lengths(emails)
    # Regenerate bodies with assigned target lengths
    for e in emails:
        # Find the scenario by group_id and scenario name
        from scenarios import ALL_SCENARIOS
        scen_map = {s.group_id: s for s in ALL_SCENARIOS}
        scenario = scen_map.get(e["group_id"])
        if scenario:
            subject, body, features = gen_body_for_scenario(
                scenario, 0, target_length_override=e["target_length"]
            )
            e["subject"] = subject
            e["body"] = body
            e["word_count"] = word_count(subject + " " + body)
    save_jsonl(emails, OUT_DIR / "dataset.jsonl")
    save_csv(emails, OUT_DIR / "dataset.csv")
    save_scenarios(OUT_DIR / "scenarios.jsonl")
    print_stats(emails)


def assign_target_lengths(emails):
    """Назначает целевую длину письма согласно целевому распределению."""
    n = len(emails)
    targets = []
    targets += ["short"] * int(n * 0.20)
    targets += ["medium"] * int(n * 0.45)
    targets += ["long"] * int(n * 0.25)
    targets += ["very_long"] * (n - len(targets))
    random.shuffle(targets)
    for e, t in zip(emails, targets):
        e["target_length"] = t
    return emails