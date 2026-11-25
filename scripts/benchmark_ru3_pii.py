"""Replay RU3 PII before/after using the actual production matcher, no DB or OCR."""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.text_match import search, tokens

CATEGORY = "pack-ru2-pii-handling"
META = {"kind", "title", "enabled", "risk", "priority"}


def documents(observed):
    suffix = "\n".join(a["text"] for a in observed["attachments"])
    full = observed["text"]
    body = full[:-len(suffix)-1] if suffix and full.endswith("\n"+suffix) else full
    return [body] + [a["text"] for a in observed["attachments"]]


def evaluate(category, docs):
    matches = []
    for rule in category["rules"]:
        if not rule["enabled"]:
            continue
        config = {k: v for k, v in rule.items() if k not in META}
        mode = config.pop("match_type", "substring")
        for i, doc in enumerate(docs):
            for start, end, score, _ in search(doc, mode=mode, **config):
                excerpt = doc[start:end]
                words = [x[0] for x in tokens(excerpt, True)]
                terms = []
                for term in rule.get("terms", []):
                    parts = [x[0] for x in tokens(term["text"], True)]
                    if parts and any(words[j:j+len(parts)] == parts for j in range(len(words))):
                        terms.append(term)
                matches.append({"rule": rule["title"], "document": i, "start": start, "end": end,
                                "score": score, "threshold": rule.get("min_score", 1),
                                "terms_in_excerpt": terms, "excerpt": excerpt})
    return matches


def metric(tp, fp, fn):
    return {"TP": tp, "FP": fp, "FN": fn,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=["pii", "internal", "financial", "pricing", "customer"], default="pii")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    category_id = {"pii": CATEGORY, "internal": "pack-ru2-internal-docs",
                   "financial": "pack-ru2-financial-plans", "pricing": "pack-ru2-pricing", "customer": "pack-ru2-customer-data"}[args.category]
    prior = json.loads((ROOT / f"config/rulepacks/history/ru3_{args.category}_before_calibration.json").read_text())
    pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
    current = next(c for c in pack["categories"] if c["id"] == category_id)
    manifest = [json.loads(x) for x in (ROOT / "test-data/benchmark-350-v1/manifest.jsonl").read_text().splitlines()]
    observations = {x["id"]: x for x in map(json.loads, (ROOT / "test-data/results-benchmark350-20261123/observations.jsonl").read_text().splitlines())}
    result = {}
    for key, cat in (("ru3_before", prior), ("ru3_after", current)):
        rows, counts = [], collections.Counter()
        per = {r["title"]: collections.Counter() for r in cat["rules"]}
        for case in manifest:
            expected = category_id in case["expected_semantic_categories"]
            hits = evaluate(cat, documents(observations[case["id"]]))
            actual = bool(hits)
            outcome = "TP" if expected and actual else "FP" if actual else "FN" if expected else "TN"
            counts[outcome] += 1
            titles = {h["rule"] for h in hits}
            for title in titles:
                per[title]["TP" if expected else "FP"] += 1
                if expected and len(titles) == 1:
                    per[title]["unique_TP"] += 1
            if outcome != "TN":
                rows.append({"id": case["id"], "scenario": case["scenario"], "outcome": outcome,
                             "hits": hits})
        result[key] = {"metrics": metric(counts["TP"], counts["FP"], counts["FN"]),
                       "per_rule": {k: dict(v) for k,v in per.items()}, "messages": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v["metrics"] for k,v in result.items()}, indent=2))


if __name__ == "__main__":
    main()
