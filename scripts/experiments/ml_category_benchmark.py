"""Frozen B350+B400 grouped TF-IDF training and later B500 evaluation.

Train and evaluate are separate commands so B500 is never read before the
model and its validation-selected thresholds are written and hashed.
"""
import argparse
import collections
import hashlib
import json
import os
import pickle
import resource
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.ml import group_hash, train, infer


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source(corpus, manifest_path, observations_path):
    manifest = read_rows(manifest_path)
    observations = {x["id"]: x for x in read_rows(observations_path)}
    if len(manifest) != len(observations) or {x["id"] for x in manifest} != set(observations):
        raise ValueError(f"{corpus}: manifest and observations differ")
    examples = []
    for row in manifest:
        observation = observations[row["id"]]
        if hashlib.sha256((Path(manifest_path).parent / row["file"]).read_bytes()).hexdigest() != observation["sha256"]:
            raise ValueError(f"{corpus}: EML hash mismatch for {row['id']}")
        examples.append(dict(id=row["id"], text=observation["text"],
                             labels=sorted(c for c in row["expected_semantic_categories"] if c.startswith("pack-ru2-")),
                             group_id=f"{corpus}:{row['scenario']}"))
    return examples


def group_split(examples):
    # Merge scenario groups that contain an identical normalized text.
    parent = {x["group_id"]: x["group_id"] for x in examples}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    by_hash = {}
    for row in examples:
        key = group_hash(row["text"])
        if key in by_hash:
            if by_hash[key]["labels"] != row["labels"]:
                raise ValueError("Conflicting labels for identical content")
            union(row["group_id"], by_hash[key]["group_id"])
        else:
            by_hash[key] = row
    groups = collections.defaultdict(list)
    for row in examples:
        groups[find(row["group_id"])].append(row)
    categories = sorted({c for row in examples for c in row["labels"]})
    names = sorted(groups)
    # Choose deterministic grouped split by class coverage and sizes, using
    # only B350/B400 labels. No B500 data enters this selection.
    best = None
    for seed in range(1000):
        shuffled = names.copy()
        np.random.default_rng(seed).shuffle(shuffled)
        n = len(shuffled)
        assigned = {g: "train" if i < int(n*.6) else "validation" if i < int(n*.8) else "test"
                    for i, g in enumerate(shuffled)}
        totals = {s: collections.Counter(c for g in names if assigned[g] == s for row in groups[g] for c in row["labels"])
                  for s in ("train", "validation", "test")}
        if not all(totals[s][c] >= 2 for s in totals for c in categories):
            continue
        # Favor balanced positive counts across validation and test.
        quality = min(totals[s][c] for s in ("validation", "test") for c in categories)
        if best is None or quality > best[0]:
            best = (quality, seed, assigned)
    if best is None:
        raise ValueError("Could not form grouped split with two positives per category in each split")
    _, seed, assigned = best
    result = []
    for row in examples:
        result.append({**row, "group_id": find(row["group_id"]), "split": assigned[find(row["group_id"])]})
    for split in ("train", "validation", "test"):
        subset = [r for r in result if r["split"] == split]
        for category in categories:
            positive = sum(category in r["labels"] for r in subset)
            if positive < 2 or positive == len(subset):
                raise ValueError(f"Invalid {split} coverage for {category}")
    return result, {"seed": seed, "groups": len(groups), "categories": categories,
                    "rows": {s: sum(r["split"] == s for r in result) for s in ("train", "validation", "test")},
                    "group_assignment": assigned}


def measure(tp, fp, fn, tn):
    return dict(TP=tp, FP=fp, FN=fn, TN=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                F1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def summarize(results, categories):
    out = {}
    for group in sorted({r["group"] for r in results} | {"ALL"}):
        subset = results if group == "ALL" else [r for r in results if r["group"] == group]
        counts = {c: [0, 0, 0, 0] for c in categories}
        for row in subset:
            for c in categories:
                e, a = c in row["expected"], c in row["actual"]
                counts[c][0 if e and a else 1 if a else 2 if e else 3] += 1
        totals = [sum(v[i] for v in counts.values()) for i in range(4)]
        per = {c: measure(*v) for c, v in counts.items()}
        vals = [v["precision"] or 0 for v in per.values()]
        macro = {key: sum((v[key] or 0) for v in per.values()) / len(per) for key in ("precision", "recall", "F1")}
        out[group] = {"messages": len(subset), "micro": measure(*totals), "macro": macro,
                      "per_category": per, "messages_with_FP": sum(bool(r["FP"]) for r in subset)}
    return out


def run_train(args):
    os.environ["OMP_NUM_THREADS"] = "2"
    examples = source("B350", args.b350_manifest, args.b350_observations) + source("B400", args.b400_manifest, args.b400_observations)
    examples, split = group_split(examples)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "split.json", split)
    save(args.output / "training_examples.json", [{k:v for k,v in r.items() if k != "text"} | {"text_sha256": group_hash(r["text"])} for r in examples])
    start = time.perf_counter()
    artifact, metrics, eligible = train(examples, min_f1=0)
    elapsed = time.perf_counter()-start
    (args.output / "tfidf.pkl").write_bytes(artifact)
    save(args.output / "training.json", {"metrics": metrics, "eligible": eligible,
         "seconds": elapsed, "maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         "artifact_bytes": len(artifact), "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
         "training_sources": [str(args.b350_manifest),str(args.b350_observations),str(args.b400_manifest),str(args.b400_observations)]})
    print("model fixed", hashlib.sha256(artifact).hexdigest(), "seconds",elapsed)


def run_evaluate(args):
    artifact = (args.model / "tfidf.pkl").read_bytes()
    training = json.loads((args.model / "training.json").read_text())
    if hashlib.sha256(artifact).hexdigest() != training["artifact_sha256"]:
        raise ValueError("Frozen model hash mismatch")
    labels = training["metrics"]["labels"]
    manifest = read_rows(args.b500_manifest)
    observations = {r["id"]: r for r in read_rows(args.b500_observations)}
    if len(manifest) != 500 or len(observations) != 500:
        raise ValueError("B500 must have exactly 500 observations")
    results = []
    start = time.perf_counter()
    for row in manifest:
        obs = observations[row["id"]]
        prediction = infer(artifact, obs["text"])
        expected = sorted(c for c in row["expected_semantic_categories"] if c in labels)
        actual = sorted(p["category"] for p in prediction if p["matched"])
        results.append({"id":row["id"], "group":row["group"],"expected":expected,"actual":actual,
                        "FP":sorted(set(actual)-set(expected)),"FN":sorted(set(expected)-set(actual)),
                        "predictions":prediction})
    elapsed = time.perf_counter()-start
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "messages.json", results)
    save(args.output / "metrics.json", summarize(results, labels) | {"inference_seconds":elapsed,
         "maxrss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         "model_sha256":training["artifact_sha256"]})
    print("B500 evaluated",elapsed)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    t=sub.add_parser("train")
    for c in ("b350","b400"):
        t.add_argument(f"--{c}-manifest",type=Path,required=True)
        t.add_argument(f"--{c}-observations",type=Path,required=True)
    t.add_argument("--output",type=Path,required=True)
    e=sub.add_parser("evaluate")
    e.add_argument("--model",type=Path,required=True)
    e.add_argument("--b500-manifest",type=Path,required=True)
    e.add_argument("--b500-observations",type=Path,required=True)
    e.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    (run_train if args.command=="train" else run_evaluate)(args)


if __name__=="__main__":
    main()
