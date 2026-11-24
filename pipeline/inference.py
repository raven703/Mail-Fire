"""Optional sequential inference with immutable input content and fenced commits."""

import hashlib
import os

from django.db import transaction

from pipeline.services import enqueue, finish, locked_current
from records.models import Content, Message, MLModel, Setting


def enabled(engine):
    # Deployment gate is independent of legacy database flags. Defaults OFF.
    return os.environ.get("MICE_" + engine.upper() + "_INFERENCE_ENABLED", "false").lower() == "true"


def route(message, key):
    kind = "ml.infer" if enabled("ml") else "llm.infer" if enabled("llm") else None
    if kind:
        return enqueue(kind, {"message_id": message.pk, "content_id": message.content_id}, "inference:" + key)
    from policy_engine.service import request_evaluation

    return request_evaluation(message.pk, key)


def run(job):
    engine = "ml" if job.kind == "ml.infer" else "llm"
    source = Content.objects.get(pk=job.payload["content_id"])
    analysis = {**source.analysis}
    findings, errors, predictions = [], [], []
    if enabled(engine):
        if engine == "ml":
            from app.ml_runtime import infer_models

            predictions, errors = infer_models(list(MLModel.objects.filter(active=True).order_by("pk")), source.text)
            # Preserve original prediction metadata; policy ML rules consume
            # predictions separately from deterministic findings.
            analysis["ml_predictions"] = predictions
            from records.models import Category

            builtin = set(Category.objects.filter(mode="builtin", active=True).values_list("pk", flat=True))
            for prediction in predictions:
                if prediction["matched"] and prediction["category"] in builtin:
                    findings.append({
                        "category": prediction["category"], "rule_id": "ml-classification", "risk": 50,
                        "confidence": prediction["confidence"], "start": 0, "end": 0, "excerpt": "",
                        "source": "supervised-ml", "version": prediction.get("model_id", ""),
                        "reason": "Вероятностная классификация; не доказательство утечки", "status": "ANALYZED",
                    })
        else:
            from app.llm_analyzer import DEFAULTS, analyze_configured
            from app.text_normalizer import DEFAULTS as NORMALIZER_DEFAULTS
            from records.models import Category

            values = {row.pk: row.value for row in Setting.objects.filter(pk__in=["llm_analyzer", "normalizer"])}
            options = DEFAULTS | values.get("llm_analyzer", {})
            findings, failures = analyze_configured(source.text, analysis.get("findings", []), options,
                NORMALIZER_DEFAULTS | values.get("normalizer", {}), dict(Category.objects.filter(active=True).values_list("pk", "name")))
            errors = [{"engine": "llm", "error": failure} for failure in failures]
        analysis["skipped_checks"] = [value for value in analysis.get("skipped_checks", []) if value != engine]
    analysis["findings"] = analysis.get("findings", []) + findings
    analysis["engine_errors"] = analysis.get("engine_errors", []) + errors
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
            following = enqueue("llm.infer", {"message_id": message.pk, "content_id": content.pk}, "llm:" + str(job.pk))
        else:
            from policy_engine.service import request_evaluation

            following = request_evaluation(message.pk, "inference:" + str(job.pk))
        finish(job.pk, job.token, {"content_id": content.pk, "next_job_id": str(following.pk), "engine": engine})