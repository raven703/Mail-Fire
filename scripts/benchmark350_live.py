"""Run the unchanged 350 EML through durable MICE acceptance and full pipeline.

No parser shortcuts, cached observations, manual detector calls or model use.
Run from the host with the existing Django environment and live workers.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mice.settings")


def write(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    temp.replace(path)


def main():
    import django
    django.setup()
    from django.utils import timezone
    from identity.models import User
    from pipeline.evidence import configuration
    from pipeline.ingestion import accept
    from pipeline.models import WorkItem
    from policy_engine.models import Evaluation
    from records.models import Attachment, Incident, Message, Policy, Setting
    from records.ocr_settings import configuration as ocr_configuration
    from records.reanalysis import request_reanalysis

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--id", help="Recover one failed EML with the same full pipeline")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "run.json").exists():
        raise ValueError("Output already has a run; preserve it and choose a new directory")
    corpus = ROOT / "test-data/benchmark-350-v1"
    manifest = [json.loads(line) for line in (corpus / "manifest.jsonl").read_text().splitlines()]
    assert len(manifest) == 350
    if args.id:
        manifest = [row for row in manifest if row['id'] == args.id]
        if len(manifest) != 1:
            raise ValueError("Unknown benchmark ID")
    run_id = uuid4().hex
    start = timezone.now()
    ocr = ocr_configuration()
    config = configuration()
    detectors = config["settings"].get("detectors", {})
    if any(detectors.get(k, True) for k in ("ml", "llm", "semantic")):
        raise ValueError("ML, LLM and semantic detectors must be explicitly disabled")
    actor = User.objects.filter(role="admin", is_active=True).first()
    if not actor:
        raise ValueError("An existing administrator is required for normal reanalysis")
    metadata = {"run_id": run_id, "started_at": start.isoformat(), "ocr_configuration": ocr,
                "configuration": config, "policies": list(Policy.objects.values()),
                "rulepack": Setting.objects.get(pk="dlp_rulepack").value,
                "manifest_sha256": hashlib.sha256((corpus / "manifest.jsonl").read_bytes()).hexdigest(),
                "method": "pipeline.ingestion.accept + records.reanalysis.request_reanalysis for duplicate blobs"}
    write(args.output / "run.json", metadata)
    pending, observations, hashes = {}, [], {}
    for row in manifest:
        data = (corpus / row["file"]).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in hashes.values():
            raise ValueError("Duplicate EML bytes need serial reanalysis: " + row["id"])
        hashes[row["id"]] = digest
        before = timezone.now()
        previous = Message.objects.filter(original_sha_ref_id=digest).values_list("content_id", flat=True).first()
        accepted = accept(data, "benchmark", f"benchmark350:{run_id}:{row['id']}", Path(row["file"]).name)
        if accepted.duplicate:
            # Acceptance of an existing blob normally evaluates its delivery.
            # Let that bookkeeping finish before requesting the full fresh parse;
            # never score that delivery evaluation of the previous analysis.
            delivery_deadline = time.monotonic() + 300
            while WorkItem.objects.filter(payload__message_id=accepted.message_id,
                                          status__in=["PENDING", "RUNNING"]).exists():
                if time.monotonic() > delivery_deadline:
                    raise TimeoutError("Existing delivery is busy: " + row["id"])
                time.sleep(0.2)
            parse = request_reanalysis(actor, accepted.message_id, run_id)
        else:
            parse = WorkItem.objects.get(deduplication_key="parse:" + accepted.message_id)
        pending[row["id"]] = {"id": row["id"], "message_id": accepted.message_id,
                              "parse_job_id": str(parse.pk), "accepted_at": before.isoformat(),
                              "previous_content_id": previous, "duplicate_blob": accepted.duplicate,
                              "sha256": digest}
    write(args.output / "input-hashes.json", hashes)
    write(args.output / "accepted.json", pending)
    deadline = time.monotonic() + args.timeout
    while pending and time.monotonic() < deadline:
        if ocr_configuration() != ocr:
            raise ValueError("OCR configuration changed during benchmark")
        if configuration() != config:
            raise ValueError("Detection configuration changed during benchmark")
        for identifier, context in list(pending.items()):
            jobs = list(WorkItem.objects.filter(payload__message_id=context["message_id"], created_at__gte=start).order_by("created_at"))
            evaluations = Evaluation.objects.filter(job__in=jobs).select_related("job", "analysis").order_by("created_at")
            evaluation = evaluations.last()
            fresh_detection = next((j for j in jobs if j.kind == "detection.detect" and j.status == "DONE"), None)
            if evaluation and (not fresh_detection or str(evaluation.job_id) != fresh_detection.output.get("policy_job_id")):
                evaluation = None
            dead = [j for j in jobs if j.status == "DEAD"]
            if not evaluation and not dead:
                continue
            message = Message.objects.select_related("content").get(pk=context["message_id"])
            content = message.content
            analysis = evaluation.analysis.results["analysis"] if evaluation else (content.analysis if content else {})
            if evaluation:
                stages = {j.kind: j for j in jobs if j.status == "DONE"}
                required = {"ingestion.parse", "extraction.extract", "ocr.complete", "detection.detect", "policy.evaluate"}
                if not required.issubset(stages):
                    raise ValueError("Missing fresh pipeline stages: " + identifier)
                if str(stages["ingestion.parse"].pk) != context["parse_job_id"]:
                    raise ValueError("Wrong parse ancestry: " + identifier)
                if context["previous_content_id"] and content.pk == context["previous_content_id"]:
                    raise ValueError("Reused cached content: " + identifier)
                if analysis.get("configuration_snapshot") != config:
                    raise ValueError("Wrong detection snapshot: " + identifier)
            incident = Incident.objects.filter(message=message).first()
            attachments = list(Attachment.objects.filter(message=message).values("id", "name", "mime", "status", "text", "details"))
            last = max((j.finished_at or j.created_at for j in jobs), default=timezone.now())
            observation = {**context, "status": message.status, "error": message.error,
                "content_id": content.pk if content else None, "text": content.text if content else "",
                "analysis": analysis, "attachments": attachments,
                "evaluation_id": str(evaluation.pk) if evaluation else None,
                "policy_hits": evaluation.hits if evaluation else [],
                "incident_id": incident.pk if incident else None,
                "seconds": (last - timezone.datetime.fromisoformat(context["accepted_at"])).total_seconds(),
                "pipeline_jobs": [{"id": str(j.pk), "kind": j.kind, "status": j.status,
                    "attempts": j.attempts, "error": j.error, "payload": j.payload,
                    "created_at": j.created_at, "started_at": j.started_at, "finished_at": j.finished_at,
                    "execution_seconds": (j.finished_at-j.started_at).total_seconds() if j.finished_at and j.started_at else None}
                    for j in jobs]}
            observations.append(observation)
            with (args.output / "observations.jsonl").open("a") as stream:
                stream.write(json.dumps(observation, ensure_ascii=False, default=str) + "\n")
            del pending[identifier]
        write(args.output / "progress.json", {"completed": len(observations), "pending": list(pending), "updated_at": timezone.now()})
        print(f"completed={len(observations)} pending={len(pending)}", flush=True)
        if pending:
            time.sleep(5)
    write(args.output / "completion.json", {"completed": len(observations), "pending": pending,
        "finished_at": timezone.now(), "ocr_unchanged": ocr_configuration() == ocr,
        "detection_configuration_unchanged": configuration() == config})
    if pending:
        raise TimeoutError("Pipeline did not complete all 350 messages")


if __name__ == "__main__":
    main()