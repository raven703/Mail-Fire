"""Train native binary SetFit/RuBERT models from the frozen grouped split.

One category per process keeps CPU/RAM bounded. Evaluation uses the native
_scores helper and frozen thresholds, never updating models from B500.
"""
import argparse
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.ml_engines import train_binary, _load_binary, _scores
from scripts.experiments.ml_category_benchmark import source, read_rows, save, summarize


def train_one(args):
    lookup = {r["id"]: r for r in json.loads((args.split / "training_examples.json").read_text())}
    rows = source("B350", args.b350_manifest, args.b350_observations) + source("B400", args.b400_manifest, args.b400_observations)
    for row in rows:
        frozen = lookup[row["id"]]
        if hashlib.sha256(" ".join(row["text"].split()).lower().encode()).hexdigest() != frozen["text_sha256"]:
            raise ValueError("Training text changed")
        row["group_id"] = frozen["group_id"]
        row["split"] = frozen["split"]
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    artifact, metrics, eligible = train_binary(rows, args.engine, args.category, min_f1=0)
    seconds = time.perf_counter()-start
    (args.output / "model.zip").write_bytes(artifact)
    save(args.output / "training.json", dict(metrics=metrics, eligible=eligible, seconds=seconds,
        maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        artifact_sha256=hashlib.sha256(artifact).hexdigest(), artifact_bytes=len(artifact),
        split_sha256=hashlib.sha256((args.split / "split.json").read_bytes()).hexdigest()))
    print(args.engine,args.category,'trained',seconds,'seconds',len(artifact),'bytes',flush=True)


def evaluate(args):
    import numpy as np
    manifest = read_rows(args.b500_manifest)
    obs = {x["id"]: x for x in read_rows(args.b500_observations)}
    categories = sorted(x.name for x in args.models.iterdir() if x.is_dir() and (x / "model.zip").is_file())
    if len(categories) != 12 or len(manifest) != 500 or len(obs) != 500:
        raise ValueError("Need 12 frozen models and all 500 B500 observations")
    scores = {}
    total_start = time.perf_counter()
    for c in categories:
        folder = args.models / c
        artifact = (folder / "model.zip").read_bytes()
        training = json.loads((folder / "training.json").read_text())
        if hashlib.sha256(artifact).hexdigest() != training["artifact_sha256"]:
            raise ValueError("Model hash mismatch")
        meta, model, tokenizer = _load_binary(training["artifact_sha256"], artifact)
        if meta["category"] != c or meta["engine"] != args.engine:
            raise ValueError("Model metadata mismatch")
        values = _scores(args.engine, model, [obs[r["id"]]["text"] for r in manifest], tokenizer)
        scores[c] = (values.tolist(), float(training["metrics"]["threshold"]))
        _load_binary.cache_clear()
    elapsed = time.perf_counter()-total_start
    results=[]
    for i,row in enumerate(manifest):
        expected=sorted(c for c in row["expected_semantic_categories"] if c in categories)
        predictions=[dict(category=c,confidence=float(scores[c][0][i]),threshold=scores[c][1],
                          matched=bool(scores[c][0][i]>=scores[c][1])) for c in categories]
        actual=sorted(p["category"] for p in predictions if p["matched"])
        results.append(dict(id=row["id"],group=row["group"],expected=expected,actual=actual,
                            FP=sorted(set(actual)-set(expected)),FN=sorted(set(expected)-set(actual)),
                            predictions=predictions))
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "messages.json",results)
    save(args.output / "metrics.json", summarize(results,categories) | dict(inference_seconds=elapsed,
         maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         model_sha256s={c:json.loads((args.models/c/"training.json").read_text())["artifact_sha256"] for c in categories}))
    print(args.engine,'B500',elapsed,'seconds',flush=True)


def main():
    os.environ["HF_HUB_OFFLINE"]="1"
    os.environ["TRANSFORMERS_OFFLINE"]="1"
    os.environ["HF_DATASETS_OFFLINE"]="1"
    os.environ["TOKENIZERS_PARALLELISM"]="false"
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest="command",required=True)
    t=s.add_parser("train")
    t.add_argument("--engine",choices=["setfit","rubert"],required=True)
    t.add_argument("--category",required=True)
    t.add_argument("--split",type=Path,required=True)
    for c in ("b350","b400"):
        t.add_argument(f"--{c}-manifest",type=Path,required=True)
        t.add_argument(f"--{c}-observations",type=Path,required=True)
    t.add_argument("--output",type=Path,required=True)
    e=s.add_parser("evaluate")
    e.add_argument("--engine",choices=["setfit","rubert"],required=True)
    e.add_argument("--models",type=Path,required=True)
    e.add_argument("--b500-manifest",type=Path,required=True)
    e.add_argument("--b500-observations",type=Path,required=True)
    e.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    (train_one if a.command=="train" else evaluate)(a)


if __name__=="__main__":main()
