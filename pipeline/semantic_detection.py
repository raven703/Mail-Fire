"""Automatic reference comparison on the existing optional semantic worker."""
import hashlib
import math
import os

from django.db import transaction

from pipeline.services import enqueue, finish, locked_current
from records.models import Attachment, Content, Message, Reference, SemanticChunk

RISK = 50
MAX_CHUNKS = 500
MAX_MATCHES = 100
DEFAULT_THRESHOLD = 0.85


def threshold():
    value = float(os.environ.get("MICE_SEMANTIC_THRESHOLD", str(DEFAULT_THRESHOLD)))
    if not math.isfinite(value) or not 0 < value <= 1:
        raise ValueError("Invalid semantic threshold")
    return value


def schedule(message, key):
    analysis = message.content.analysis
    config = analysis.get("configuration_snapshot", {})
    if not config.get("settings", {}).get("detectors", {}).get("semantic", True):
        return None
    if "SEMANTIC_REFERENCE" in config.get("inactive_categories", []):
        return None
    # Keep only references present at deterministic-analysis time.
    refs = sorted(str(row["id"]) for row in config.get("references", [])
                  if not (row.get("fingerprint") or {}).get("document_template"))
    try:
        minimum = threshold()
    except ValueError:
        minimum = None  # worker records a configuration error, not a clean result
    return enqueue("semantic.detect", {"message_id": message.pk, "content_id": message.content_id,
                                      "reference_ids": refs, "threshold": minimum},
                   "semantic-detect:" + key)


def documents(source, message_id):
    length = source.analysis.get("semantic_body_length")
    if not isinstance(length, int) or not 0 <= length <= len(source.text):
        raise ValueError("Missing semantic body boundary")
    return [("body", "", source.text[:length])] + [
        (row.pk, row.name, row.text) for row in
        Attachment.objects.filter(message_id=message_id).order_by("pk")
    ]


def compare_documents(parts, references, minimum):
    from pgvector.django import CosineDistance
    from records.semantic import MODEL, chunks, vectors

    if minimum is None or not math.isfinite(minimum) or not 0 < minimum <= 1:
        raise ValueError("Invalid semantic threshold")
    if not references:
        return [], [], "NO_REFERENCES"
    names = dict(Reference.objects.filter(pk__in=references).values_list("pk", "name"))
    indexed = SemanticChunk.objects.filter(source_type="reference", source_id__in=names, model=MODEL)
    available = set(indexed.values_list("source_id", flat=True).distinct())
    missing = set(references) - available
    errors = [{"engine": "semantic", "error": "reference_index_unavailable", "count": len(missing)}] if missing else []
    if not available:
        return [], errors, "PARTIAL"
    pending = [(identifier, filename, index, fragment)
               for identifier, filename, text in parts
               for index, fragment in enumerate(chunks(text))]
    if len(pending) > MAX_CHUNKS:
        errors.append({"engine": "semantic", "error": "document_chunk_limit"})
        pending = pending[:MAX_CHUNKS]
    best = {}
    for offset in range(0, len(pending), 16):
        batch = pending[offset:offset + 16]
        for (identifier, filename, index, fragment), vector in zip(batch, vectors([p[3] for p in batch]), strict=True):
            matches = indexed.annotate(distance=CosineDistance("embedding", vector)).filter(
                distance__lte=1 - minimum).order_by("distance", "source_id", "chunk_index").values(
                    "source_id", "chunk_index", "text", "distance")[:MAX_MATCHES + 1]
            rows = list(matches)
            if len(rows) > MAX_MATCHES and not any(e["error"] == "match_limit" for e in errors):
                errors.append({"engine": "semantic", "error": "match_limit"})
            for row in rows[:MAX_MATCHES]:
                similarity = max(0.0, min(1.0, 1 - float(row["distance"])))
                key = (identifier, row["source_id"])
                if key in best and best[key]["confidence"] >= similarity:
                    continue
                best[key] = {
                    "category": "SEMANTIC_REFERENCE", "source": "semantic-reference",
                    "rule_id": row["source_id"], "reference_id": row["source_id"],
                    "reference_name": names[row["source_id"]], "document_id": identifier,
                    "filename": filename, "risk": RISK, "confidence": similarity,
                    "similarity_percent": round(similarity * 100, 1), "semantic_threshold": minimum,
                    "chunk_index": index, "reference_chunk_index": row["chunk_index"],
                    "excerpt": fragment[:500], "reference_excerpt": row["text"][:500],
                    "start": 0, "end": 0, "version": MODEL,
                    "reason": "Семантическое сходство; требуется проверка аналитиком", "status": "ANALYZED",
                }
    hits = sorted(best.values(), key=lambda hit: (-hit["confidence"], hit["document_id"], hit["reference_id"]))
    if len(hits) > MAX_MATCHES:
        errors.append({"engine": "semantic", "error": "finding_limit"})
    return hits[:MAX_MATCHES], errors, "PARTIAL" if errors else "OK"


def persist(job, findings, errors, state):
    """Caller owns the job lock and transaction; do not overwrite newer evidence."""
    from pipeline.inference import route
    message = Message.objects.select_for_update().filter(pk=job.payload["message_id"]).first()
    if message is None or message.content_id != job.payload["content_id"] or message.status == "PENDING":
        return {"superseded": True}
    source = message.content
    analysis = dict(source.analysis)
    analysis["findings"] = [f for f in analysis.get("findings", [])
                            if f.get("source") != "semantic-reference"] + findings
    analysis["engine_errors"] = list(analysis.get("engine_errors", [])) + errors
    skipped = set(analysis.get("skipped_checks", []))
    if state in {"OK", "PARTIAL"}:
        skipped.discard("semantic")
    else:
        skipped.add("semantic")
    analysis["skipped_checks"] = sorted(skipped)
    analysis["semantic_detection"] = {"status": state, "threshold": job.payload["threshold"],
                                      "reference_ids": job.payload["reference_ids"], "matches": len(findings)}
    content, _ = Content.objects.get_or_create(
        normalized_sha=hashlib.sha256(("semantic:" + str(job.pk) + "\\0" + source.pk).encode()).hexdigest(),
        defaults={"text": source.text, "analysis": analysis, "version": source.version})
    message.content = content
    if errors:
        message.status = "PARTIAL"
        message.error = "Incomplete analysis; see engine_errors/attachments"
    message.save(update_fields=["content", "status", "error"])
    following = route(message, "semantic:" + str(job.pk), after_semantic=True)
    return {"content_id": content.pk, "next_job_id": str(following.pk), "status": state}


def run(job):
    from pipeline.inference import enabled
    source = Content.objects.get(pk=job.payload["content_id"])
    if not enabled("semantic"):
        findings, errors, state = [], [{"engine": "semantic", "error": "deployment_disabled"}], "PARTIAL"
    else:
        try:
            findings, errors, state = compare_documents(
                documents(source, job.payload["message_id"]), job.payload["reference_ids"], job.payload["threshold"])
        except Exception as exc:
            # Do not log message text, reference excerpts or exception details.
            from django.db import OperationalError
            if isinstance(exc, OperationalError):
                raise
            findings, errors, state = [], [{"engine": "semantic", "error": type(exc).__name__}], "PARTIAL"
    with transaction.atomic():
        locked_current(job.pk, job.token)
        output = persist(job, findings, errors, state)
        finish(job.pk, job.token, output)
