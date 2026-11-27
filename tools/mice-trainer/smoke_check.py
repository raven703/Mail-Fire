"""Real end-to-end CUDA training and CPU reloading; all artifacts stay outside Git."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CLI = Path(__file__).resolve().with_name("trainer.py")
HOME = Path.home() / "mice-trainer-data"


def main():
    run_dir = HOME / "output" / ("smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    run_dir.mkdir(parents=True)
    log_dir = HOME / "logs" / run_dir.name
    log_dir.mkdir(parents=True)

    def run(name, *args, cpu=False):
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        if cpu:
            env["CUDA_VISIBLE_DEVICES"] = ""
        with (log_dir / f"{name}.log").open("w") as log:
            subprocess.run([sys.executable, str(CLI), *map(str, args)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)

    run("doctor", "doctor", "--require-cuda")
    dataset = run_dir / "smoke.jsonl"
    run("dataset", "smoke-data", "--output", dataset)
    rows = [json.loads(line) for line in dataset.read_text().splitlines()]
    external = run_dir / "external.jsonl"
    # An independent plumbing fixture, NOT a realistic semantic quality benchmark.
    with external.open("w") as out:
        for row in rows[:8]:
            row.update(id="external-" + row["id"], group_id="external-" + row["group_id"],
                       subject="Независимый технический пример " + row["subject"],
                       body=row["body"] + " Другой источник.")
            row.pop("split", None)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    categories = ("pack-ru2-financial-plans", "pack-ru2-pricing")
    results = []
    for engine in ("tfidf", "setfit", "rubert"):
        for category in ([None] if engine == "tfidf" else categories):
            name = engine + ("-" + category if category else "")
            folder = run_dir / name
            extra = [] if category is None else ["--category", category, "--max-steps", "3"]
            run(name, "train", "--engine", engine, "--device", "auto", "--seed", "42",
                "--dataset", dataset, "--output", folder, *extra)
            meta = json.loads((folder / "training.json").read_text())
            if category:
                assert meta["metrics"]["training_device"] == "cuda"
            partitions = json.loads((folder / "split.json").read_text())
            sets = [{r["group_id"] for r in partitions if r["split"] == split}
                    for split in ("train", "validation", "test")]
            assert all(not a & b for i, a in enumerate(sets) for b in sets[i + 1:])
            run(name + "-cpu", "evaluate", "--model", folder, "--dataset", external,
                "--output", folder / "external.json", cpu=True)
            if category is None or category == categories[0]:
                repeat = run_dir / (name + "-repeat")
                run(name + "-repeat", "train", "--engine", engine, "--device", "auto", "--seed", "42",
                    "--dataset", dataset, "--output", repeat, *extra)
                other = json.loads((repeat / "training.json").read_text())
                assert meta["metrics"] == other["metrics"], f"Metrics differ: {name}"
                assert (folder / "split.json").read_bytes() == (repeat / "split.json").read_bytes()
                run(name + "-repeat-cpu", "evaluate", "--model", repeat, "--dataset", external,
                    "--output", repeat / "external.json", cpu=True)
                original_eval = json.loads((folder / "external.json").read_text())
                repeated_eval = json.loads((repeat / "external.json").read_text())
                assert original_eval["categories"] == repeated_eval["categories"]
                # Compare actual CPU scores, not only aggregate/confusion metrics.
                for target, suffix in ((folder, "original"), (repeat, "repeated")):
                    run(name + "-" + suffix, "predict", "--model", target,
                        "--text", "Закрытый бюджет и непубличная скидка", cpu=True)
                def scores(suffix):
                    text = (log_dir / f"{name}-{suffix}.log").read_text()
                    return json.loads(text[text.index('[\n'):])
                assert scores("original") == scores("repeated"), f"CPU scores differ: {name}"
            results.append(dict(engine=engine, category=category, metrics=meta["metrics"],
                                artifact_sha256=meta["artifact_sha256"], cpu_reload=True))
            print(f"PASS {name}", flush=True)
    (run_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(f"All checks passed. Artifacts: {run_dir}; logs: {log_dir}")


if __name__ == "__main__":
    main()