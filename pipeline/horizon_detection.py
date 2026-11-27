"""Optional Horizon work on the existing neural queue, fenced and fail-open."""

import hashlib
from types import SimpleNamespace

from django.db import OperationalError, transaction

from pipeline.services import enqueue, finish, locked_current
from records.models import Content, Message


def schedule(message, key):
    if message.content.analysis.get("horizon_detection"):
        return None
    config = message.content.analysis.get("configuration_snapshot", {})
    if not config.get("settings", {}).get("detectors", {}).get("horizon", False):
        return None
    if not any(r["kind"] == "horizon" for b in config.get("groups", []) for r in b["rules"]):
        return None
    return enqueue(
        "horizon.infer",
        {"message_id": message.pk, "content_id": message.content_id, "configuration": config},
        "horizon:" + key,
    )


def evaluate_documents(parts, config, ml_predictions=(), *, cached=None, references=()):
    from app.categories import evaluate_groups
    from app.horizon import MAX_PAIRS, MAX_WINDOWS, analyze_document, score_pairs
    from functools import partial

    device = config.get("settings", {}).get("horizon_detection", {}).get("device", "cpu")

    groups = [
        {"category": SimpleNamespace(**b["category"]), "rules": [SimpleNamespace(**r) for r in b["rules"]]}
        for b in config.get("groups", [])
    ]
    rules = [r for b in groups for r in b["rules"] if r.kind == "horizon"]
    findings, errors, checks = [], [], []
    budget = {"pairs": MAX_PAIRS, "windows": MAX_WINDOWS}
    for identifier, filename, text in parts:
        if not text.strip():
            continue
        if cached is None:
            predicted, failures = analyze_document(text, rules, budget=budget, scorer=partial(score_pairs, device=device))
        else:
            predicted, failures = cached.get(identifier, {}), []
        errors.extend(dict(e, document_id=identifier) for e in failures)
        scores = {"horizon:" + key: value for key, value in predicted.items()}
        local_ml = [p for p in ml_predictions if p.get("document_id", "body") == identifier]
        for p in local_ml:
            scores.setdefault(p["category"], []).append(p)
        engines = {"keywords", "regex", "horizon"}
        if local_ml:
            engines.add("ml")
        # Full category ANY/ALL evaluated per source, with all applicable evidence.
        local_references = [
            {**r, "reference_id": r.get("reference_id", r.get("rule_id"))}
            for r in references
            if r.get("document_id") == identifier and r.get("source") in {"fingerprint", "custom-reference"}
        ]
        if local_references:
            engines.add("reference")
        normalized = None
        options = config.get("settings", {}).get("normalizer", {})
        if options.get("enabled") and config.get("settings", {}).get("detectors", {}).get("normalizer", True):
            from app.evidence import normalized_variant

            normalized = normalized_variant(text, options.get("sensitivity", "medium"))
        local = evaluate_groups(
            groups,
            text,
            ml_scores=scores,
            references=local_references,
            available_engines=engines,
            normalized=normalized,
        )
        for hit in local:
            hit.update(
                document_id=identifier,
                filename=filename,
                source_label="Вложение" if filename else "Тело письма",
            )
        findings.extend(local)
        checks.append(
            {
                "document_id": identifier,
                "rules_evaluated": list(predicted),
                "partial": bool(failures),
                "predictions": predicted,
            }
        )
    return findings, errors, checks


def run(job):
    from pipeline.inference import enabled
    from pipeline.semantic_detection import documents

    source = Content.objects.get(pk=job.payload["content_id"])
    message = Message.objects.get(pk=job.payload["message_id"])
    if message.status == "PENDING" or (
        message.content_id != source.pk
        and (
            message.content.text != source.text
            or message.content.analysis.get("analysis_generation")
            != source.analysis.get("analysis_generation")
            or message.content.analysis.get("configuration_snapshot")
            != source.analysis.get("configuration_snapshot")
        )
    ):
        with transaction.atomic():
            locked_current(job.pk, job.token)
            finish(job.pk, job.token, {"superseded": True})
        return
    try:
        if not enabled("horizon"):
            raise RuntimeError("Horizon deployment disabled")
        parts = documents(source, message.pk)
        findings, errors, checks = evaluate_documents(
            parts,
            job.payload["configuration"],
            source.analysis.get("ml_predictions", []),
            references=source.analysis.get("findings", []),
        )
    except OperationalError:
        raise
    except Exception as exc:
        findings, errors, checks = [], [{"engine": "horizon", "error": type(exc).__name__}], []
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=message.pk)
        current = message.content
        # Optional sibling inference may have advanced content. Merge into latest
        # only when original extraction and rule snapshot are still identical.
        if (
            message.status == "PENDING"
            or current.text != source.text
            or current.analysis.get("analysis_generation") != source.analysis.get("analysis_generation")
            or current.analysis.get("configuration_snapshot") != source.analysis.get("configuration_snapshot")
        ):
            finish(job.pk, job.token, {"superseded": True})
            return
        analysis = dict(current.analysis)
        if checks:
            findings, _, _ = evaluate_documents(
                parts,
                job.payload["configuration"],
                analysis.get("ml_predictions", []),
                cached={r["document_id"]: r["predictions"] for r in checks},
                references=analysis.get("findings", []),
            )
        existing = analysis.get("findings", [])
        from app.evidence import unique_findings

        # Refresh only categories for which Horizon returned a complete result.
        # A failed optional method must never delete independent custom evidence.
        complete = {c["document_id"] for c in checks if not c["partial"]}
        horizon_categories = {b["category"]["id"] for b in job.payload["configuration"].get("groups", [])
                              if any(r["kind"] == "horizon" for r in b["rules"])}
        analysis["findings"] = unique_findings([
            f for f in existing if not (
                f.get("source", "").startswith("custom-")
                and f.get("document_id", "body") in complete
                and f.get("category") in horizon_categories)
        ] + findings)
        analysis["engine_errors"] = [
            e for e in analysis.get("engine_errors", []) if e.get("engine") != "horizon"
        ] + errors
        analysis["skipped_checks"] = sorted(
            (set(analysis.get("skipped_checks", [])) - {"horizon"}) | ({"horizon"} if errors else set())
        )
        analysis["horizon_detection"] = {"status": "PARTIAL" if errors else "OK", "checks": checks}
        content, _ = Content.objects.get_or_create(
            normalized_sha=hashlib.sha256(
                ("horizon:" + str(job.pk) + "\0" + current.pk).encode()
            ).hexdigest(),
            defaults={"text": current.text, "analysis": analysis, "version": current.version},
        )
        message.content = content
        if errors:
            message.status = "PARTIAL"
        message.save(update_fields=["content", "status"])
        from policy_engine.service import request_evaluation

        following = request_evaluation(message.pk, "horizon:" + str(job.pk))
        finish(
            job.pk,
            job.token,
            {"status": analysis["horizon_detection"]["status"], "next_job_id": str(following.pk)},
        )


def terminal_failure(job):
    """Worker hard failure: retain other evidence and explicitly mark incomplete."""
    message = Message.objects.select_for_update().filter(pk=job.payload.get("message_id")).first()
    if not message or message.status == "PENDING" or not message.content_id:
        return
    source = Content.objects.filter(pk=job.payload.get("content_id")).first()
    current = message.content
    if (
        not source
        or source.text != current.text
        or source.analysis.get("analysis_generation") != current.analysis.get("analysis_generation")
        or source.analysis.get("configuration_snapshot") != current.analysis.get("configuration_snapshot")
    ):
        return
    analysis = dict(current.analysis)
    analysis["engine_errors"] = list(analysis.get("engine_errors", [])) + [
        {"engine": "horizon", "error": "worker_terminal_failure"}
    ]
    analysis["skipped_checks"] = sorted(set(analysis.get("skipped_checks", [])) | {"horizon"})
    analysis["horizon_detection"] = {"status": "PARTIAL", "checks": []}
    content, _ = Content.objects.get_or_create(
        normalized_sha=hashlib.sha256(("horizon-terminal:" + str(job.pk)).encode()).hexdigest(),
        defaults={"text": current.text, "analysis": analysis, "version": current.version},
    )
    message.content, message.status = content, "PARTIAL"
    message.save(update_fields=["content", "status"])
    from policy_engine.service import request_evaluation

    request_evaluation(message.pk, "horizon-terminal:" + str(job.pk))
