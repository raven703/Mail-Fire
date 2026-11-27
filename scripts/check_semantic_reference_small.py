"""Small real-model/pgvector calibration, never against a production database.

Run with DJANGO_SETTINGS_MODULE=mice.settings and a migrated disposable DB.
Reference/index writes are rolled back. Model must already be cached offline.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mice.settings")
import django
django.setup()

from django.conf import settings
from django.db import transaction
from pipeline.semantic_detection import compare_documents
from pipeline.services import claim, enqueue
from records.references import save_reference
from records.semantic import MODEL, reindex


def main():
    database = settings.DATABASES["default"]["NAME"]
    if not (database.startswith("test_") or database.startswith("pr36_")):
        raise SystemExit("Use a disposable test_/pr36_ database")
    directory = Path(__file__).resolve().parents[1] / "test-data/semantic-reference-small"
    corpus = json.loads((directory / "corpus.json").read_text())
    references = {row["id"]: row["text"] for row in corpus["references"]}
    results = []
    with transaction.atomic():
        ids = []
        for identifier, text in references.items():
            row = save_reference(SimpleNamespace(pk="pr36-corpus"), {
                "data": text.encode(), "name": identifier, "text": text, "fingerprint": {}})
            ids.append(row.pk)
        job = enqueue("semantic.reindex", {"items": [["reference", pk] for pk in ids]}, "small:" + uuid4().hex)
        reindex(claim(job.pk, "small-corpus"))
        for query in corpus["queries"]:
            text = references[query["reference"]] if query.get("reference") else query["text"]
            # Threshold sweep uses actual pgvector scores, not mocked vectors.
            hits, errors, state = compare_documents([("body", "", text)], ids, .01)
            assert not errors and state == "OK", (state, errors)
            score = max((hit["confidence"] for hit in hits), default=0)
            results.append({"id": query["id"], "kind": query["kind"], "positive": query["positive"], "score": score})
        transaction.set_rollback(True)
    metrics = []
    for value in range(70, 96, 5):
        minimum = value / 100
        tp = sum(row["positive"] and row["score"] >= minimum for row in results)
        fp = sum(not row["positive"] and row["score"] >= minimum for row in results)
        fn = sum(row["positive"] and row["score"] < minimum for row in results)
        tn = len(results) - tp - fp - fn
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        metrics.append({"threshold": minimum, "TP": tp, "FP": fp, "FN": fn, "TN": tn,
                        "precision": precision, "recall": recall,
                        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0})
    best = max(metrics, key=lambda row: (row["f1"], -row["FP"], row["threshold"]))
    report = {"model": MODEL, "corpus_sha256": hashlib.sha256((directory / "corpus.json").read_bytes()).hexdigest(),
              "unit": "document; any reference match", "references": len(references), "queries": results,
              "metrics": metrics, "recommended_threshold_on_this_corpus": best["threshold"],
              "limitations": "Synthetic small Russian corpus; calibration only, not held-out production validation."}
    (directory / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()