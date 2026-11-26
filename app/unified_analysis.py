"""One isolated request owns the deterministic analysis of one mail."""
import base64
import time
import uuid

from app.config import settings


def analyze_message(payload, ocr):
    from app.mail import parse_mail
    from app.extraction import extract
    from app.ocr_evidence import evidence
    from app.detection_evidence import analyze
    from app.advanced_detectors import static_scan

    started = time.monotonic()
    original = base64.b64decode(payload["original"], validate=True)
    if not original or len(original) > settings().max_message_bytes:
        raise ValueError("Message limit")
    config = payload["configuration"]
    parsed = parse_mail(original)
    timings = {"mail": time.monotonic() - started}
    raw = parsed.pop("attachments")
    if len(raw) > settings().max_objects:
        raise ValueError("Attachment count limit")
    rows, documents = [], [{"id": "body", "text": parsed["text"]}]
    budget = [0, 0]
    start = time.monotonic()
    for name, mime, data in raw:
        text, status, details = extract(data, name, budget=budget, use_ocr=False)
        required = bool(details.get("ocr_required"))
        attempted = required and payload["ocr_enabled"]
        if attempted:
            result = ocr(data, name)
            text, status, details = result["text"], result["status"], result["details"]
        details = {**details, **evidence(details, status, required=required,
                                        enabled=payload["ocr_enabled"], attempted=attempted)}
        identifier = str(uuid.uuid4())
        rows.append({"id": identifier, "name": name, "mime": mime, "text": text,
                     "status": status, "details": details,
                     "data": base64.b64encode(data).decode()})
        documents.append({"id": identifier, "text": text})
    timings["extraction_ocr"] = time.monotonic() - start
    start = time.monotonic()
    combined = "\n".join(d["text"] for d in documents)
    result = analyze({"text": combined, "configuration": config, "documents": documents,
                      "attachments": [{k: v for k, v in r.items() if k != "data"} for r in rows]})
    timings["detection"] = time.monotonic() - start
    start = time.monotonic()
    enabled = config["settings"].get("detectors", {})
    engines = {key: enabled.get(key, True) for key in ("static_files", "secrets")}
    if any(engines.values()):
        objects = [("body", "body.txt", parsed["text"].encode())]
        objects.extend((row["id"], name, data) for row, (name, _, data) in zip(rows, raw))
        for identifier, name, data in objects:
            try:
                scanned = static_scan(data, name, engines=engines)
                result["findings"].extend({**hit, "document_id": identifier} for hit in scanned["findings"])
                for engine, state in scanned["engines"].items():
                    if state not in {"OK", "DISABLED"}:
                        result["engine_errors"].append({"engine": engine, "error": state})
            except Exception as exc:
                result["engine_errors"].append({"engine": "static_scan", "error": type(exc).__name__})
    else:
        result["skipped_checks"].extend(engines)
    for row in rows:
        result["findings"].extend(row["details"].get("findings", []))
    timings["static_scan"] = time.monotonic() - start
    return {"parsed": parsed, "attachments": rows, "text": combined, "evidence": result,
            "timings": timings}
