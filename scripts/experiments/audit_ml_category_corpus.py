"""Audit frozen B-350/B-400 labels and the built-in ML split without training.

Usage: python scripts/experiments/audit_ml_category_corpus.py \
  --b350-manifest PATH --b350-observations PATH \
  --b400-manifest PATH --b400-observations PATH --output PATH
The optional neural split audit runs only when scikit-learn is installed.
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.ml import group_hash


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def category_labels(item):
    return tuple(sorted(c for c in item["expected_semantic_categories"] if c.startswith("pack-ru2-")))


def audit(sources):
    examples = []
    source_hashes = {}
    for name, manifest_path, observations_path in sources:
        manifest, observations = rows(manifest_path), rows(observations_path)
        by_id = {item["id"]: item for item in observations}
        if len(by_id) != len(observations) or {r["id"] for r in manifest} != set(by_id):
            raise ValueError(f"{name}: IDs do not match")
        source_hashes[name] = {"manifest_sha256": hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
                               "observations_sha256": hashlib.sha256(Path(observations_path).read_bytes()).hexdigest()}
        root = Path(manifest_path).parent
        for row in manifest:
            observation = by_id[row["id"]]
            if hashlib.sha256((root / row["file"]).read_bytes()).hexdigest() != observation["sha256"]:
                raise ValueError(f"{name}: EML hash differs for {row['id']}")
            examples.append({"id": row["id"], "corpus": name, "template": name + ":" + row["scenario"],
                             "group": row.get("group"), "text": observation["text"],
                             "labels": category_labels(row), "status": observation["status"]})
    categories = sorted({label for item in examples for label in item["labels"]})
    by_hash = collections.defaultdict(list)
    by_template = collections.defaultdict(list)
    for example in examples:
        by_hash[group_hash(example["text"])].append(example)
        by_template[example["template"]].append(example)
    conflicts = [{"ids": [x["id"] for x in group], "labels": [x["labels"] for x in group]}
                 for group in by_hash.values() if len({x["labels"] for x in group}) > 1]
    template_conflicts = [{"template": key, "labels": sorted({x["labels"] for x in group})}
                          for key, group in by_template.items() if len({x["labels"] for x in group}) > 1]
    # Exact implementation of app.ml.train: sorted distinct group hashes,
    # NumPy default_rng(42), then 60/20/20. No model is fitted here.
    keys = sorted(by_hash)
    np.random.default_rng(42).shuffle(keys)
    n = len(keys)
    splits = {"train": keys[:int(n * 0.6)], "validation": keys[int(n * 0.6):int(n * 0.8)],
              "test": keys[int(n * 0.8):]}
    split_of = {key: split for split, members in splits.items() for key in members}
    template_splits = {template: sorted({split_of[group_hash(x["text"])] for x in group})
                       for template, group in by_template.items()}
    tfidf_leaks = {key: value for key, value in template_splits.items() if len(value) > 1}
    # The native neural trainer uses a second random stratified split per
    # category. It also has no template/group argument; measure it when deps exist.
    neural = {}
    try:
        from app.ml_engines import _binary_data
        inputs = [{"text": x["text"], "labels": x["labels"]} for x in examples]
        for category in categories:
            parts = _binary_data(inputs, category)
            locations = collections.defaultdict(set)
            for split, (texts, _) in parts.items():
                for text in texts:
                    for original in by_hash[group_hash(text)]:
                        locations[original["template"]].add(split)
            leaks = sorted(k for k, v in locations.items() if len(v) > 1)
            neural[category] = {"split_sizes": {k: len(v[0]) for k, v in parts.items()},
                                "templates_in_multiple_splits": len(leaks), "leak_examples": leaks[:10]}
    except ImportError as exc:
        neural = {"unavailable": str(exc)}
    return {"source_hashes": source_hashes, "rows": len(examples), "categories": categories,
            "source_counts": dict(collections.Counter(x["corpus"] for x in examples)),
            "status_counts": dict(collections.Counter(x["status"] for x in examples)),
            "exact_unique_texts": len(by_hash), "exact_duplicate_rows": len(examples)-len(by_hash),
            "exact_label_conflicts": conflicts, "scenario_label_conflicts": template_conflicts,
            "scenario_groups": len(by_template), "tfidf_native_split_sizes": {k: len(v) for k, v in splits.items()},
            "tfidf_scenarios_in_multiple_splits": len(tfidf_leaks),
            "tfidf_leak_examples": dict(list(sorted(tfidf_leaks.items()))[:20]),
            "neural_native_splits": neural,
            "finding": "Native trainers split by individual text hash, not semantic scenario. Threshold validation is contaminated when scenario variants span splits."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for corpus in ("b350", "b400"):
        parser.add_argument(f"--{corpus}-manifest", type=Path, required=True)
        parser.add_argument(f"--{corpus}-observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit([(name, getattr(args, name + "_manifest"), getattr(args, name + "_observations"))
                    for name in ("b350", "b400")])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("rows", "exact_duplicate_rows", "exact_label_conflicts",
                                        "scenario_groups", "tfidf_scenarios_in_multiple_splits")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
