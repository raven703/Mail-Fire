"""Standalone MICE training CLI. Run with the trainer virtual environment."""
# ruff: noqa: E402 -- direct CLI invocation requires the checkout on sys.path
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ml import group_hash, train
from app.ml_engines import train_binary
from app.ml_runtime import infer_models
from app.ml_split import partition

CATEGORIES = ("pack-ru2-financial-plans", "pack-ru2-pricing")
HOME = Path.home() / "mice-trainer-data"
BASE = HOME / "base_models" / "rubert-tiny2"
PACKAGES = ("torch", "numpy", "scikit-learn", "transformers", "setfit",
            "sentence-transformers", "datasets", "accelerate", "safetensors", "pydantic-settings")


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def doctor(args):
    import platform

    import torch
    info = {"python": sys.version, "platform": platform.platform(),
            "versions": {p: version(p) for p in PACKAGES},
            "cuda_available": torch.cuda.is_available(), "cuda_build": torch.version.cuda}
    if torch.cuda.is_available():
        x = torch.ones((512, 512), device="cuda")
        info.update(gpu=torch.cuda.get_device_name(0), cuda_matmul=float((x @ x)[0, 0]),
                    vram_bytes=torch.cuda.get_device_properties(0).total_memory)
    for name in ("datasets", "base_models", "output", "logs"):
        (HOME / name).mkdir(parents=True, exist_ok=True)
    dump(HOME / "logs" / "doctor.json", info)
    print(json.dumps(info, indent=2))
    if args.require_cuda and not info["cuda_available"]:
        raise RuntimeError("CUDA required but unavailable")


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
        if (not isinstance(labels, list) or not all(isinstance(v, str) and v.strip() for v in labels)
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


def prepare(rows, categories=None, seed=42):
    categories = categories or sorted({c for r in rows for c in r["labels"]})
    if not categories:
        raise ValueError("No categories selected")
    by_hash = {group_hash(row["text"]): row for row in rows}
    parts = partition(by_hash, seed=seed)
    counts = {}
    for split, keys in parts.items():
        subset = [by_hash[k] for k in keys]
        counts[split] = {"total": len(subset)}
        for category in categories:
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
    from app.trainer_package import versions

    if not 0 <= args.min_f1 <= 1:
        raise ValueError("min_f1 must be between 0 and 1")
    rows = read_rows(args.dataset)
    categories = args.categories or ([args.category] if args.category else sorted({c for r in rows for c in r["labels"]}))
    if args.category and args.categories:
        raise ValueError("Use --category or --categories, not both")
    if args.engine == "tfidf":
        for row in rows:
            row["labels"] = [c for c in row["labels"] if c in categories]
    counts = prepare(rows, categories, args.seed)
    print(json.dumps(counts, ensure_ascii=False, indent=2), flush=True)
    if args.engine == "tfidf" and args.category:
        raise ValueError("TF-IDF is global; omit --category")
    if args.engine != "tfidf" and not args.category:
        raise ValueError("Neural training requires --category")
    if args.engine != "tfidf" and args.categories:
        raise ValueError("Neural engines export one binary model; use --category per run")
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
        artifact, metrics, eligible = train(rows, min_f1=args.min_f1, seed=args.seed)
        filename = "model.pkl"
    else:
        artifact, metrics, eligible = train_binary(
            rows, args.engine, args.category, args.min_f1, device=args.device,
            batch_size=args.batch_size, epochs=args.epochs, max_steps=args.max_steps, show_progress=True, seed=args.seed)
        filename = "model.zip"
    meta = {"format": 1, "engine": args.engine, "category_id": args.category,
            "artifact": filename, "artifact_sha256": sha(artifact),
            "dataset_sha256": sha(args.dataset.read_bytes()),
            "split_sha256": sha((args.output / "split.json").read_bytes()),
            "metrics": metrics, "eligible": bool(eligible),
            "versions": versions(),
             "python": sys.version, "seed": args.seed}
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
    groups = {r["group_id"] for r in used}
    rows = read_rows(args.dataset)
    if any(group_hash(r["text"]) in hashes or r["group_id"] in groups for r in rows):
        raise ValueError("Evaluation contains a text or group already seen during training/validation/test")
    categories = meta["metrics"]["labels"] if model.engine == "tfidf" else (model.category_id,)
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
    p = sub.add_parser("run-job")
    p.add_argument("job", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=run_job)
    p = sub.add_parser("doctor")
    p.add_argument("--require-cuda", action="store_true")
    p.set_defaults(func=doctor)
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
    p.add_argument("--category")
    p.add_argument("--categories", nargs="+")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
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
    # Capture library progress, stdout and stderr in a separate process: unlike
    # redirect_stdout this also captures native extension and Trainer messages.
    if args.command == "train" and not os.environ.get("MICE_TRAINER_LOG_CHILD"):
        import subprocess

        logs = HOME / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        log = logs / f"{stamp}-{args.engine}.log"
        print(f"Training log: {log}", flush=True)
        env = dict(os.environ, MICE_TRAINER_LOG_CHILD="1", PYTHONUNBUFFERED="1")
        with log.open("x", encoding="utf-8") as stream:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, env=env)
            try:
                for line in process.stdout:
                    stream.write(line)
                    stream.flush()
                    print(line, end="", flush=True)
                code = process.wait()
            except KeyboardInterrupt:
                process.terminate()
                process.wait()
                raise
        raise SystemExit(code)
    args.func(args)


def read_job(path):
    """Validate before creating outputs or loading neural libraries."""
    import math

    job = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "dataset", "categories", "engines", "device", "epochs",
                "batch_size", "max_steps", "seed", "min_f1", "output"}
    if not isinstance(job, dict) or required - job.keys() or job.keys() - required - {"evaluation_dataset", "base"}:
        raise ValueError("Missing or unknown job fields")
    if not isinstance(job["name"], str) or not job["name"].strip():
        raise ValueError("Job name must be nonempty")
    for key in ("categories", "engines"):
        values = job[key]
        if (not isinstance(values, list) or not values or
                not all(isinstance(v, str) and v.strip() for v in values) or len(values) != len(set(values))):
            raise ValueError(f"Invalid {key}")
    if set(job["engines"]) - {"tfidf", "setfit", "rubert"} or job["device"] not in ("auto", "cpu", "cuda"):
        raise ValueError("Invalid engines/device")
    if "tfidf" in job["engines"] and len(job["categories"]) < 2:
        raise ValueError("TF-IDF requires at least two categories")
    for key in ("epochs", "batch_size", "max_steps", "seed"):
        if type(job[key]) is not int or job[key] < (0 if key == "seed" else 1):
            raise ValueError(f"Invalid {key}")
    if (type(job["min_f1"]) not in (int, float) or not math.isfinite(job["min_f1"]) or
            not 0 <= job["min_f1"] <= 1):
        raise ValueError("Invalid min_f1")
    for key in ("dataset", "evaluation_dataset", "output", "base"):
        if key not in job or job[key] is None:
            continue
        if not isinstance(job[key], str) or not job[key].strip():
            raise ValueError(f"Invalid {key} path")
        value = Path(job[key]).expanduser()
        job[key] = (path.resolve().parent / value).resolve()
    if job.get("base") is None:
        job["base"] = BASE
    if job["output"].exists():
        raise FileExistsError(job["output"])
    rows = read_rows(job["dataset"])
    if not 30 <= len(rows) <= 10000:
        raise ValueError("Native engines require 30–10000 examples")
    counts = prepare(rows, job["categories"], job["seed"])
    evaluation = job.get("evaluation_dataset")
    if evaluation:
        external = read_rows(evaluation)
        hashes = {group_hash(r["text"]) for r in rows}
        groups = {r["group_id"] for r in rows}
        ids = {r["id"] for r in rows}
        if any(group_hash(r["text"]) in hashes or r["group_id"] in groups or r["id"] in ids for r in external):
            raise ValueError("Evaluation dataset overlaps training dataset")
        for category in job["categories"]:
            if not 0 < sum(category in r["labels"] for r in external) < len(external):
                raise ValueError(f"Evaluation lacks positive/negative coverage: {category}")
    plan = [{"engine": engine, "category_id": category}
            for engine in job["engines"]
            for category in ([None] if engine == "tfidf" else job["categories"])]
    return job, rows, {"name": job["name"], "model_count": len(plan), "models": plan,
                       "split_counts": counts, "device": job["device"],
                       "independent_evaluation": bool(evaluation)}


def run_job(args):
    from contextlib import redirect_stderr, redirect_stdout

    from app.trainer_package import versions, write_package

    job, rows, plan = read_job(args.job)
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if args.dry_run:
        return plan
    output = job["output"]
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "plan.json", plan)
    # Persist one split and feed exactly these assignments to every native engine.
    split = [{k: r[k] for k in ("id", "group_id", "split")} for r in rows]
    dump(output / "split.json", split)
    prepared = output / ".job-input.jsonl"
    models = []
    report = {"name": job["name"], "status": "running", "models": []}
    try:
        prepared.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        for index, item in enumerate(plan["models"], 1):
            folder = output / f"model-{index}"
            options = SimpleNamespace(**{k: job[k] for k in
                ("seed", "base", "device", "batch_size", "epochs", "max_steps", "min_f1")},
                dataset=prepared, output=folder, engine=item["engine"], category=item["category_id"],
                categories=job["categories"] if item["engine"] == "tfidf" else None)
            with (output / f"model-{index}.log").open("x", encoding="utf-8") as log:
                with redirect_stdout(log), redirect_stderr(log):
                    training(options)
                    if job.get("evaluation_dataset"):
                        evaluate(SimpleNamespace(model=folder, dataset=job["evaluation_dataset"],
                                                 output=folder / "evaluation.json"))
            meta = json.loads((folder / "training.json").read_text())
            labels = meta["metrics"]["labels"]
            meta.update(categories=labels, versions=versions(),
                        thresholds=meta["metrics"].get("thresholds", [meta["metrics"].get("threshold")]))
            if job.get("evaluation_dataset"):
                meta["independent_evaluation"] = json.loads((folder / "evaluation.json").read_text())
            models.append((meta, (folder / meta["artifact"]).read_bytes()))
            report["models"].append({"engine": meta["engine"], "categories": labels,
                                     "eligible": meta["eligible"], "metrics": meta["metrics"],
                                     "independent_evaluation": meta.get("independent_evaluation")})
        report["status"] = "completed"
        write_package(output / "models.zip", models, report)
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        prepared.unlink(missing_ok=True)
        dump(output / "report.json", report)
    return report


if __name__ == "__main__":
    main()
