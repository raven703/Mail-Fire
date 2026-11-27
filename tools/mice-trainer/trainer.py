"""Standalone MICE training CLI. Run with the trainer virtual environment."""
import argparse
import hashlib
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ml import group_hash, train
from app.ml_split import partition
from app.ml_engines import train_binary
from app.ml_runtime import infer_models

CATEGORIES = ("pack-ru2-financial-plans", "pack-ru2-pricing")
HOME = Path.home() / "mice-trainer-data"
BASE = HOME / "base_models" / "rubert-tiny2"
PACKAGES = ("torch", "numpy", "scikit-learn", "transformers", "setfit",
            "sentence-transformers", "datasets", "accelerate", "safetensors", "pydantic-settings")


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    rows, ids, hashes = [], set(), set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_no}: expected object")
        ident, group, labels = (row.get(k) for k in ("id", "group_id", "labels"))
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(f"Line {line_no}: missing or duplicate id")
        if not isinstance(group, str) or not group.strip():
            raise ValueError(f"Line {line_no}: missing group_id")
        if (not isinstance(labels, list) or not all(isinstance(v, str) and v in CATEGORIES for v in labels)
                or len(labels) != len(set(labels))):
            raise ValueError(f"Line {line_no}: invalid labels")
        if "text" in row:
            value = row["text"]
        else:
            subject, body = row.get("subject", ""), row.get("body", "")
            if not isinstance(subject, str) or not isinstance(body, str):
                raise ValueError(f"Line {line_no}: invalid subject/body")
            value = subject.strip() + "\n" + body.strip()
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Line {line_no}: empty text")
        value = value.strip()
        key = group_hash(value)
        if key in hashes:
            raise ValueError(f"Line {line_no}: duplicate normalized text")
        ids.add(ident)
        hashes.add(key)
        result = dict(id=ident, group_id=group, labels=sorted(labels), text=value)
        if "split" in row:
            result["split"] = row["split"]
        rows.append(result)
    if not rows:
        raise ValueError("Empty dataset")
    return rows


def prepare(rows):
    by_hash = {group_hash(row["text"]): row for row in rows}
    parts = partition(by_hash)
    counts = {}
    for split, keys in parts.items():
        subset = [by_hash[k] for k in keys]
        counts[split] = {"total": len(subset)}
        for category in CATEGORIES:
            positives = sum(category in r["labels"] for r in subset)
            if not 0 < positives < len(subset):
                raise ValueError(f"{split}: insufficient positive/negative coverage for {category}")
            counts[split][category] = positives
        for row in subset:
            row["split"] = split
    return counts


def download(args):
    from huggingface_hub import HfApi, snapshot_download
    from app.config import settings
    from app.ml_engines import _base_path

    repo = "cointegrated/rubert-tiny2"
    revision = HfApi().model_info(repo, revision=args.revision).sha
    args.base.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=repo, revision=revision, local_dir=str(args.base),
                      ignore_patterns=["*.onnx", "*.h5", "*.msgpack", "*.ot"])
    os.environ["ML_RUBERT_BASE_PATH"] = str(args.base.resolve())
    os.environ["ML_SETFIT_BASE_PATH"] = str(args.base.resolve())
    settings.cache_clear()
    for engine in ("setfit", "rubert"):
        _base_path(engine)
    dump(args.base / "mice-source.json", {"repo": repo, "revision": revision})
    print(f"Base snapshot: {args.base} ({revision})")


def training(args):
    rows = read_rows(args.dataset)
    counts = prepare(rows)
    print(json.dumps(counts, ensure_ascii=False, indent=2), flush=True)
    if args.engine == "tfidf" and args.category:
        raise ValueError("TF-IDF is global; omit --category")
    if args.engine != "tfidf" and not args.category:
        raise ValueError("Neural training requires --category")
    if args.engine != "tfidf":
        from app.config import settings
        from app.ml_engines import _base_path
        os.environ["ML_RUBERT_BASE_PATH"] = str(args.base.resolve())
        os.environ["ML_SETFIT_BASE_PATH"] = str(args.base.resolve())
        settings.cache_clear()
        _base_path(args.engine)
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / "split.json", [{"id": r["id"], "group_id": r["group_id"], "split": r["split"],
                                       "text_sha256": group_hash(r["text"]), "labels": r["labels"]} for r in rows])
    if args.engine == "tfidf":
        artifact, metrics, eligible = train(rows, min_f1=args.min_f1)
        filename = "model.pkl"
    else:
        artifact, metrics, eligible = train_binary(
            rows, args.engine, args.category, args.min_f1, device=args.device,
            batch_size=args.batch_size, epochs=args.epochs, max_steps=args.max_steps, show_progress=True)
        filename = "model.zip"
    meta = {"format": 1, "engine": args.engine, "category_id": args.category,
            "artifact": filename, "artifact_sha256": sha(artifact),
            "dataset_sha256": sha(args.dataset.read_bytes()),
            "split_sha256": sha((args.output / "split.json").read_bytes()),
            "metrics": metrics, "eligible": bool(eligible),
            "versions": {p: version(p) for p in PACKAGES},
            "python": sys.version}
    source = args.base / "mice-source.json"
    if args.engine != "tfidf" and source.is_file():
        meta["base_source"] = json.loads(source.read_text())
    (args.output / filename).write_bytes(artifact)
    dump(args.output / "training.json", meta)
    print(json.dumps({"eligible": bool(eligible), "validation": metrics["validation"],
                      "test": metrics["test"], "output": str(args.output)}, ensure_ascii=False, indent=2))


def load_model(folder):
    # This is intentionally a trusted-local-artifact workflow. Hashes detect
    # corruption, not malicious pickle or checkpoint content.
    meta = json.loads((folder / "training.json").read_text())
    expected = "model.pkl" if meta["engine"] == "tfidf" else "model.zip"
    if meta["artifact"] != expected or meta["engine"] not in ("tfidf", "setfit", "rubert"):
        raise ValueError("Invalid artifact metadata")
    raw = (folder / expected).read_bytes()
    if sha(raw) != meta["artifact_sha256"]:
        raise ValueError("Artifact SHA-256 mismatch")
    return SimpleNamespace(id=1, engine=meta["engine"], category_id=meta["category_id"],
                           artifact=raw, metrics=meta["metrics"]), meta


def predict(args):
    model, _ = load_model(args.model)
    predictions, errors = infer_models([model], args.text)
    if errors:
        raise RuntimeError(str(errors))
    print(json.dumps(predictions, ensure_ascii=False, indent=2))


def evaluate(args):
    model, meta = load_model(args.model)
    split_file = args.model / "split.json"
    if sha(split_file.read_bytes()) != meta["split_sha256"]:
        raise ValueError("Split SHA-256 mismatch")
    used = json.loads(split_file.read_text())
    hashes = {r["text_sha256"] for r in used}
    rows = read_rows(args.dataset)
    if any(group_hash(r["text"]) in hashes for r in rows):
        raise ValueError("Evaluation contains text already seen during training/validation/test")
    categories = CATEGORIES if model.engine == "tfidf" else (model.category_id,)
    counts = {c: dict(tp=0, fp=0, fn=0, tn=0) for c in categories}
    for row in rows:
        preds, errors = infer_models([model], row["text"])
        if errors:
            raise RuntimeError(str(errors))
        by_category = {p["category"]: p for p in preds}
        for c in categories:
            truth, hit = c in row["labels"], by_category[c]["matched"]
            counts[c]["tp" if truth and hit else "fn" if truth else "fp" if hit else "tn"] += 1
    for v in counts.values():
        tp, fp, fn = v["tp"], v["fp"], v["fn"]
        v.update(precision=tp / max(1, tp + fp), recall=tp / max(1, tp + fn),
                 f1=2 * tp / max(1, 2 * tp + fp + fn))
    result = {"rows": len(rows), "dataset_sha256": sha(args.dataset.read_bytes()),
              "artifact_sha256": meta["artifact_sha256"], "categories": counts}
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        dump(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def smoke_data(args):
    # Deliberately simple plumbing fixture; NEVER use it for quality estimates.
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        for i in range(60):
            group = i // 4
            labels = [[], [CATEGORIES[0]], [CATEGORIES[1]], list(CATEGORIES)][i % 4]
            text = ["Встреча по ремонту оборудования", "Закрытый бюджет будущего года",
                    "Индивидуальная непубличная скидка", "Внутренний прогноз выручки и закрытая цена"][i % 4]
            row = dict(id=f"smoke-{i}", group_id=f"smoke-group-{group}",
                       labels=labels, subject=f"Тест {i}", body=f"{text}. Пример {i}.",
                       split="train" if group < 9 else "validation" if group < 12 else "test")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("download-base")
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--revision", default="main")
    p.set_defaults(func=download)
    p = sub.add_parser("smoke-data")
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=smoke_data)
    p = sub.add_parser("train")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--engine", choices=("tfidf", "setfit", "rubert"), required=True)
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--epochs", type=int)
    p.add_argument("--max-steps", type=int)
    p.add_argument("--min-f1", type=float, default=0.7)
    p.set_defaults(func=training)
    p = sub.add_parser("predict")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=predict)
    p = sub.add_parser("evaluate")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.set_defaults(func=evaluate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
