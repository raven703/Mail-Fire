"""Optional sequential inference with immutable input content and fenced commits."""

import hashlib
import json
import os
from types import SimpleNamespace

from django.db import transaction

from pipeline.services import enqueue, finish, locked_current
from records.models import Content, InferenceArtifact, Message, MLModel, Setting


def enabled(engine):
    # Deployment gate is independent of legacy database flags. Defaults OFF.
    return os.environ.get("MICE_" + engine.upper() + "_INFERENCE_ENABLED", "false").lower() == "true"


def route(message, key, *, after_semantic=False):
    if not after_semantic and enabled("semantic"):
        from pipeline.semantic_detection import schedule
        job = schedule(message, key)
        if job is not None:
            # Optional inference must never hold deterministic findings hostage
            # when its worker is stopped. Evaluate them now; semantic completion
            # queues a newer evaluation through the existing fenced path.
            from policy_engine.service import request_evaluation
            request_evaluation(message.pk, "before-semantic:" + key)
            return job
    kind = "ml.infer" if enabled("ml") else "llm.infer" if enabled("llm") else None
    if kind:
        model_snapshots = []
        if enabled("ml"):
            for row in MLModel.objects.filter(active=True).order_by("pk"):
                data = bytes(row.artifact)
                sha = hashlib.sha256(data).hexdigest()
                InferenceArtifact.objects.get_or_create(pk=sha, defaults={"data": data})
                model_snapshots.append({"id": row.pk, "engine": row.engine, "category_id": row.category_id,
                                        "metrics": row.metrics, "sha256": sha})
        snapshot = {
            "models": model_snapshots,
            "settings": {row.pk: row.value for row in Setting.objects.filter(pk__in=["llm_analyzer", "normalizer"])},
        }
        from records.models import Category

        snapshot["categories"] = list(Category.objects.filter(active=True).values("id", "name", "mode"))
        if any(row["engine"] in {"setfit", "rubert"} for row in snapshot["models"]):
            kind = "neural.infer"
        return enqueue(kind, {"message_id": message.pk, "content_id": message.content_id, "snapshot": snapshot}, "inference:" + key)
    from policy_engine.service import request_evaluation

    return request_evaluation(message.pk, key)


def run(job):
    engine = "llm" if job.kind == "llm.infer" else "ml"
    snapshot = job.payload["snapshot"]
    source = Content.objects.get(pk=job.payload["content_id"])
    analysis = {**source.analysis}
    findings, errors, predictions = [], [], []
    if enabled(engine):
        if engine == "ml":
            from app.ml_runtime import infer_models

            models = []
            for metadata in snapshot["models"]:
                row = InferenceArtifact.objects.filter(pk=metadata["sha256"]).first()
                if row is None or hashlib.sha256(bytes(row.data)).hexdigest() != metadata["sha256"]:
                    errors.append({"model_id": metadata["id"], "error": "snapshot_artifact_unavailable"})
                    continue
                models.append(SimpleNamespace(id=metadata["id"], engine=metadata["engine"],
                                              category_id=metadata["category_id"], metrics=metadata["metrics"], artifact=bytes(row.data)))
            predictions, failures = infer_models(models, source.text)
            errors.extend(failures)
            # Preserve original prediction metadata; policy ML rules consume
            # predictions separately from deterministic findings.
            analysis["ml_predictions"] = predictions
            builtin = {row["id"] for row in snapshot["categories"] if row["mode"] == "builtin"}
            for prediction in predictions:
                if prediction["matched"] and prediction["category"] in builtin:
                    findings.append({
                        "category": prediction["category"], "rule_id": "ml-classification", "risk": 50,
                        "confidence": prediction["confidence"], "start": 0, "end": 0, "excerpt": "",
                        "source": "supervised-ml", "version": prediction.get("model_id", ""),
                        "reason": "Вероятностная классификация; не доказательство утечки", "status": "ANALYZED",
                    })
            from pipeline.parser_client import call

            evaluated = call("detection_evidence", json.dumps({
                "text": source.text, "configuration": analysis["configuration_snapshot"], "attachments": [],
                "ml_scores": {p["category"]: p for p in predictions}, "ml_available": bool(models),
            }).encode())
            analysis["findings"] = [f for f in analysis.get("findings", []) if not f.get("source", "").startswith("custom-")]
            findings.extend(f for f in evaluated["findings"] if f.get("source", "").startswith("custom-"))
            if models:
                analysis["engine_errors"] = [e for e in analysis.get("engine_errors", []) if e.get("engine") != "category_ml"]
        else:
            from app.llm_analyzer import DEFAULTS, analyze_configured
            from app.text_normalizer import DEFAULTS as NORMALIZER_DEFAULTS
            values = snapshot["settings"]
            options = DEFAULTS | values.get("llm_analyzer", {})
            findings, failures = analyze_configured(source.text, analysis.get("findings", []), options,
                NORMALIZER_DEFAULTS | values.get("normalizer", {}), {row["id"]: row["name"] for row in snapshot["categories"]})
            errors = [{"engine": "llm", "error": failure} for failure in failures]
        analysis["skipped_checks"] = [value for value in analysis.get("skipped_checks", []) if value != engine]
    analysis["findings"] = analysis.get("findings", []) + findings
    analysis["engine_errors"] = analysis.get("engine_errors", []) + errors
    analysis["inference_snapshot"] = snapshot
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=job.payload["message_id"])
        if message.content_id != source.pk:
            finish(job.pk, job.token, {"superseded": True})
            return
        content, _ = Content.objects.get_or_create(
            normalized_sha=hashlib.sha256((str(job.pk) + "\0" + source.pk).encode()).hexdigest(),
            defaults={"text": source.text, "analysis": analysis, "version": source.version},
        )
        message.content = content
        if errors:
            message.status = "PARTIAL"
        message.save(update_fields=["content", "status"])
        if engine == "ml" and enabled("llm"):
            following = enqueue("llm.infer", {"message_id": message.pk, "content_id": content.pk, "snapshot": snapshot}, "llm:" + str(job.pk))
        else:
            from policy_engine.service import request_evaluation

            following = request_evaluation(message.pk, "inference:" + str(job.pk))
        finish(job.pk, job.token, {"content_id": content.pk, "next_job_id": str(following.pk), "engine": engine})