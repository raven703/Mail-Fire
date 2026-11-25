"""Read-only replay of current RU3 against published RU3 baseline with production matcher."""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_ru3_pii import documents, evaluate, metric

HISTORY = {
    "pii-handling": "pii", "internal-docs": "internal", "financial-plans": "financial",
    "pricing": "pricing", "customer-data": "customer",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
    manifest = [json.loads(x) for x in (ROOT / "test-data/benchmark-350-v1/manifest.jsonl").read_text().splitlines()]
    obs = {x["id"]: x for x in map(json.loads, (ROOT / "test-data/results-benchmark350-20261123/observations.jsonl").read_text().splitlines())}
    result = {}
    for version in ("before", "after"):
        total = collections.Counter()
        result[version] = {"categories": {}}
        for current in pack["categories"]:
            cid = current["id"]
            suffix = cid.removeprefix("pack-ru2-")
            prior = ROOT / f"config/rulepacks/history/ru3_{HISTORY.get(suffix, suffix)}_before_calibration.json"
            cat = json.loads(prior.read_text()) if version == "before" and prior.exists() else current
            count = collections.Counter()
            per_rule = {r["title"]: collections.Counter() for r in cat["rules"]}
            errors = []
            for row in manifest:
                exp = cid in row["expected_semantic_categories"]
                hits = evaluate(cat, documents(obs[row["id"]]))
                actual = bool(hits)
                status = "TP" if exp and actual else "FP" if actual else "FN" if exp else "TN"
                count[status] += 1
                titles = {h["rule"] for h in hits}
                for title in titles:
                    per_rule[title]["TP" if exp else "FP"] += 1
                    if exp and len(titles) == 1:
                        per_rule[title]["unique_TP"] += 1
                if status in ("FP", "FN"):
                    errors.append({"id": row["id"], "scenario": row["scenario"], "outcome": status, "hits": hits})
            total.update(count)
            result[version]["categories"][cid] = {"metrics": metric(count["TP"], count["FP"], count["FN"]),
                "per_rule": {k: dict(v) for k,v in per_rule.items()}, "errors": errors}
        result[version]["micro"] = metric(total["TP"], total["FP"], total["FN"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({v: r["micro"] for v,r in result.items()}, indent=2))


if __name__ == "__main__":
    main()
