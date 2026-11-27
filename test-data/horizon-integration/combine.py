"""Exploratory B500 fusion from saved predictions only. Never imports inference."""

import base64
import csv
import gzip
import hashlib
import itertools
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HORIZON = "d846b91"
ML = "19cdc936f342e2b7330fb07e1b5815a8dd604bcd"
BASELINE = "e3f5d016667d8db939b614055334fb50442d4899"


def save_gzip(path, text):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(text.encode())


def artifact(ref, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ref}:{path}"])


def measure(y, p):
    tp = sum(a and b for a, b in zip(y, p))
    fp = sum(not a and b for a, b in zip(y, p))
    fn = sum(a and not b for a, b in zip(y, p))
    tn = len(y) - tp - fp - fn
    return dict(
        TP=tp,
        TN=tn,
        FP=fp,
        FN=fn,
        precision=tp / (tp + fp) if tp + fp else 0,
        recall=tp / (tp + fn) if tp + fn else 0,
        F1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
    )


def main():
    provenance = {}

    def read(ref, path, compressed=False):
        ref = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", ref], text=True).strip()
        raw = artifact(ref, path)
        provenance[f"{ref}:{path}"] = hashlib.sha256(raw).hexdigest()
        return json.loads(gzip.decompress(base64.b64decode(raw)) if compressed else raw)

    raw = artifact(HORIZON, "test-data/horizon-benchmark/predictions.jsonl")
    provenance["horizon_predictions"] = hashlib.sha256(raw).hexdigest()
    horizon = [json.loads(line) for line in raw.splitlines() if json.loads(line)["corpus"] == "b500"]
    methods = {f"horizon-{d}": [r for r in horizon if r["dtype"] == d] for d in ("fp32", "fp16")}
    for engine in ("ru3", "ru4"):
        methods[engine] = read(BASELINE, f"test-data/results-benchmark500-v1/{engine}/messages.json")
    for engine in ("tfidf", "setfit", "rubert"):
        methods[engine] = read(
            ML, f"test-data/results-ml-category-benchmark/{engine}-b500/messages.json.gz.b64", True
        )
    manifest_raw = artifact(BASELINE, "test-data/benchmark-500-v1/manifest.jsonl")
    manifest = [json.loads(line) for line in manifest_raw.splitlines()]
    expected = {r["id"]: sorted(r["expected_semantic_categories"]) for r in manifest}
    ids = sorted(expected)
    categories = sorted({c for values in expected.values() for c in values})
    assert len(ids) == 500 and len(categories) == 12
    obs_raw = artifact(BASELINE, "test-data/results-benchmark500-v1/observations.jsonl")
    observations = {r["id"]: r for r in (json.loads(line) for line in obs_raw.splitlines())}
    experiment = read(ML, "test-data/results-ml-category-benchmark/experiment.json")
    assert hashlib.sha256(obs_raw).hexdigest() == experiment["input_hashes"]["b500"]["observations_sha256"]
    assert hashlib.sha256(manifest_raw).hexdigest() == experiment["input_hashes"]["b500"]["manifest_sha256"]
    model_rows = {}
    for engine, values in methods.items():
        assert len(values) == 500 and len({r["id"] for r in values}) == 500
        mapping = {r["id"]: r for r in values}
        assert set(mapping) == set(ids)
        assert all(sorted(mapping[i]["expected"]) == expected[i] for i in ids)
        assert all(set(mapping[i]["actual"]) <= set(categories) for i in ids)
        if engine.startswith("horizon"):
            assert all(
                mapping[i]["text_sha256"] == hashlib.sha256(observations[i]["text"].encode()).hexdigest()
                for i in ids
            )
        model_rows[engine] = {i: set(mapping[i]["actual"]) for i in ids}
    safe = [i for i in ids if not expected[i]]
    assert len(safe) == 260

    def summarize(pred, members):
        per = {c: measure([c in expected[i] for i in ids], [c in pred[i] for i in ids]) for c in categories}
        result = dict(
            micro=measure(
                [c in expected[i] for i in ids for c in categories],
                [c in pred[i] for i in ids for c in categories],
            ),
            macro_F1=sum(m["F1"] for m in per.values()) / 12,
            per_category=per,
            safe_messages_with_FP=sum(bool(pred[i]) for i in safe),
            safe_messages=260,
        )
        result["attribution"] = {}
        for engine in members:
            own = model_rows[engine]
            others = {i: set().union(*(model_rows[e][i] for e in members if e != engine)) for i in ids}
            result["attribution"][engine] = dict(
                rescued_positive_decisions=sum(
                    c in pred[i] and c not in own[i] for i in ids for c in expected[i]
                ),
                uniquely_contributed_TP=[
                    {"id": i, "category": c}
                    for i in ids
                    for c in expected[i]
                    if c in pred[i] and c in own[i] and c not in others[i]
                ],
                uniquely_contributed_FP=[
                    {"id": i, "category": c}
                    for i in ids
                    for c in sorted(pred[i] - set(expected[i]))
                    if c in own[i] and c not in others[i]
                ],
                participating_FP=sum(c in own[i] for i in ids for c in pred[i] - set(expected[i])),
            )
        return result

    results, predictions = {}, {}
    for engine in methods:
        predictions[engine] = model_rows[engine]
        results[engine] = summarize(predictions[engine], [engine])
    recommendations = {}
    for dtype in ("fp32", "fp16"):
        h = f"horizon-{dtype}"
        # FP32 and FP16 are alternatives, NEVER two independent votes.
        all_methods = [h, "ru3", "ru4", "tfidf", "setfit", "rubert"]
        combos = [(f"{h}+{e}", [h, e], 1) for e in ("ru4", "setfit", "rubert", "tfidf")]
        combos += [
            (f"{h}+ru4+setfit", [h, "ru4", "setfit"], 1),
            (f"{dtype}:all-ANY", all_methods, 1),
            (f"{dtype}:at-least-two", all_methods, 2),
        ]
        for name, members, votes in combos:
            pred = {
                i: {c for c in categories if sum(c in model_rows[e][i] for e in members) >= votes}
                for i in ids
            }
            predictions[name] = pred
            results[name] = dict(members=members, minimum_votes=votes, **summarize(pred, members))
        chosen, grid = {}, []
        for c in categories:
            options = []
            for n in range(1, len(all_methods) + 1):
                for members in itertools.combinations(all_methods, n):
                    for votes in (1, 2):
                        if votes > n:
                            continue
                        p = {
                            i: c in {c} and sum(c in model_rows[e][i] for e in members) >= votes for i in ids
                        }
                        m = measure([c in expected[i] for i in ids], [p[i] for i in ids])
                        safe_fp = sum(p[i] for i in safe)
                        option = dict(
                            category=c, members=list(members), minimum_votes=votes, safe_FP=safe_fp, **m
                        )
                        options.append(option)
            # Safety-aware development recommendation, explicitly exploratory.
            # Require precision >= .85, at most 2 safe FPs and at least 5/25 TP.
            feasible = [o for o in options if o["precision"] >= 0.85 and o["safe_FP"] <= 2 and o["TP"] >= 5]
            if feasible:
                pick = max(
                    feasible,
                    key=lambda o: (
                        o["recall"],
                        -o["safe_FP"],
                        o["precision"],
                        -len(o["members"]),
                        o["minimum_votes"],
                    ),
                )
                chosen[c] = dict(**pick, recommendation="shadow-only; new-corpus validation required")
            else:
                pick = max(
                    options,
                    key=lambda o: (
                        o["precision"] if o["TP"] >= 5 else -1,
                        -o["safe_FP"],
                        o["recall"],
                        -len(o["members"]),
                    ),
                )
                chosen[c] = dict(
                    **pick,
                    recommendation="not recommended for automated use; no candidate meets safety constraints",
                )
            grid.extend(options)
        name = f"{dtype}:per-category-exploratory"
        pred = {
            i: {
                c
                for c, cfg in chosen.items()
                if sum(c in model_rows[e][i] for e in cfg["members"]) >= cfg["minimum_votes"]
            }
            for i in ids
        }
        predictions[name] = pred
        results[name] = dict(
            **summarize(pred, all_methods), warning="Selected on B500, not independent quality validation"
        )
        recommendations[dtype] = chosen
        save_gzip(
            HERE / f"category-grid-{dtype}.jsonl.gz", "".join(json.dumps(option) + "\n" for option in grid)
        )
    for filename, value in [
        ("metrics.json", results),
        ("recommendations.json", recommendations),
        (
            "provenance.json",
            {
                "source_hashes": provenance,
                "observations_sha256": hashlib.sha256(obs_raw).hexdigest(),
                "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
                "verified_ids": 500,
                "verified_categories": categories,
                "labels_equal": True,
                "horizon_text_hashes_equal": True,
                "historical_text_provenance": "Exact observations SHA256 matches ML experiment; legacy prediction rows omit text hashes",
                "warning": "Exploratory combination selection on previously used B500, not independent evaluation",
                "recommendation_policy": "precision>=.85, safe_FP<=2, TP>=5; then max recall, fewer safe FP, higher precision, fewer methods. Otherwise do not recommend automated use.",
            },
        ),
    ]:
        (HERE / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "summary.csv").open("w") as f:
        records = [
            dict(method=name, **m["micro"], macro_F1=m["macro_F1"], safe_FP=m["safe_messages_with_FP"])
            for name, m in results.items()
        ]
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    save_gzip(
        HERE / "combined-predictions.jsonl.gz",
        "".join(
            json.dumps(dict(method=name, id=i, expected=expected[i], actual=sorted(pred[i]))) + "\n"
            for name, pred in predictions.items()
            for i in ids
        ),
    )
    print((HERE / "summary.csv").read_text())


if __name__ == "__main__":
    main()
