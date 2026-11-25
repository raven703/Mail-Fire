"""Replay frozen extracted text: no OCR, mail writes, training or network."""

import argparse
import collections
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def metrics(count):
    tp, fp, fn = (count[k] for k in ("TP", "FP", "FN"))
    return {**dict(count), "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from app import text_match
    from app.categories import evaluate_groups
    from policy_engine.rules import policy_matches

    original_search = text_match.search
    old_search = module("baseline_matcher", args.baseline_dir / "text_match_before.py").search
    old_evaluate = module("baseline_categories", args.baseline_dir / "categories_before.py").evaluate_groups
    corpus = ROOT / "test-data/benchmark-350-v1"
    result_dir = ROOT / "test-data/results-benchmark350-20261123"
    manifests = [json.loads(line) for line in (corpus / "manifest.jsonl").read_text().splitlines()]
    observations = {r["id"]: r for r in map(json.loads, (result_dir / "observations.jsonl").read_text().splitlines())}
    semantic = {c for row in manifests for c in row["expected_semantic_categories"] if c.startswith("pack-ru2-")}
    summary = {"scope": "frozen extracted text; 12 custom categories only", "messages": len(manifests),
               "normalization_enabled": False, "engines": {}, "hashes": {}}
    for path in (corpus / "manifest.jsonl", result_dir / "config.json", result_dir / "observations.jsonl"):
        summary["hashes"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    detailed = []
    for name, filename, evaluator, matcher in (
        ("ru2_before", "ru2_morph_weighted_rules.json", old_evaluate, old_search),
        ("ru3_after", "ru3_candidate.json", evaluate_groups, original_search),
    ):
        pack = json.loads((ROOT / "config/rulepacks" / filename).read_text())
        summary["hashes"][filename] = hashlib.sha256((ROOT / "config/rulepacks" / filename).read_bytes()).hexdigest()
        groups = []
        for cat in pack["categories"]:
            rules = []
            for index, rule in enumerate(cat["rules"]):
                metadata = {k: rule[k] for k in ("kind", "title", "enabled", "risk", "priority")}
                rules.append(SimpleNamespace(id=f"{cat['id']}:{index}", **metadata,
                             config={k: v for k, v in rule.items() if k not in metadata}))
            groups.append({"category": SimpleNamespace(id=cat["id"], name=cat["name"], mode="custom",
                                                       match_mode=cat["match_mode"]), "rules": rules})
        text_match.search = matcher
        total = collections.Counter(TP=0, FP=0, FN=0)
        per_category = {c: collections.Counter(TP=0, FP=0, FN=0) for c in semantic}
        per_split = collections.defaultdict(lambda: collections.Counter(TP=0, FP=0, FN=0))
        per_policy = collections.defaultdict(lambda: collections.Counter(TP=0, FP=0, FN=0))
        started = time.monotonic()
        for row in manifests:
            observed = observations[row["id"]]
            if hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest() != observed["sha256"]:
                raise ValueError("Original mail hash mismatch: " + row["id"])
            if name == "ru2_before":
                findings = evaluator(groups, observed["text"])
            else:
                suffix = "\n".join(a["text"] for a in observed["attachments"])
                full = observed["text"]
                body = full[:-len(suffix)-1] if suffix and full.endswith("\n"+suffix) else full
                findings = []
                for index, text in enumerate([body] + [a["text"] for a in observed["attachments"]]):
                    findings.extend({**h, "document_id": str(index)} for h in evaluator(groups, text))
            expected = set(row["expected_semantic_categories"]) & semantic
            actual = {f["category"] for f in findings} & semantic
            count = dict(TP=len(expected & actual), FP=len(actual-expected), FN=len(expected-actual))
            total.update(count)
            per_split[row.get("evaluation_split", "unspecified")].update(count)
            for c in semantic:
                if c in expected or c in actual:
                    per_category[c]["TP" if c in expected & actual else "FP" if c in actual else "FN"] += 1
            for policy in pack["policies"]:
                relevant = set(policy.get("categories", [])) & semantic
                if not relevant:
                    continue
                exp = bool(expected & relevant)
                act = bool(policy_matches(findings, policy))
                if exp or act:
                    per_policy[policy["name"]]["TP" if exp and act else "FP" if act else "FN"] += 1
            detailed.append({"engine": name, "id": row["id"], "expected": sorted(expected),
                             "actual": sorted(actual), **count, "findings": len(findings)})
        summary["engines"][name] = {"micro": metrics(total), "seconds": time.monotonic()-started,
            "per_category": {k: metrics(v) for k, v in sorted(per_category.items())},
            "per_split": {k: metrics(v) for k, v in sorted(per_split.items())},
            "per_policy_custom_scope": {k: metrics(v) for k, v in sorted(per_policy.items())}}
    text_match.search = original_search
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (args.output / "messages.json").write_text(json.dumps(detailed, ensure_ascii=False, indent=2))
    print(json.dumps({k: v["micro"] for k, v in summary["engines"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()