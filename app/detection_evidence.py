"""Persistence-free deterministic analysis using the original MICE algorithms."""

from types import SimpleNamespace


def analyze(payload):
    from app.advanced_detectors import pii
    from app.categories import evaluate_groups
    from app.detectors import VERSION, detect
    from app.document_templates import finding_for_template
    from app.fingerprints import compare
    from app.text_normalizer import DEFAULTS
    from app.evidence import normalized_variant, unique_findings

    text, config = payload["text"], payload["configuration"]
    options = {**DEFAULTS, **config["settings"].get("normalizer", {})}
    from app.detector_catalog import DETECTORS

    enabled = config["settings"].get("detectors", {})
    disabled = {category for key, value in DETECTORS.items() if not enabled.get(key, True) for category in value[2]}
    disabled.update(config.get("inactive_categories", []))
    normalization = {"enabled": bool(options["enabled"] and enabled.get("normalizer", True)), "transforms": []}
    # Never combine context from different MIME documents. Older callers without
    # documents retain the single-source API, but the mail pipeline supplies them.
    documents = payload.get("documents", [{"id": "message", "text": text}])
    from app.text_match import CompiledRuleSet, PreparedDocument
    compiled = CompiledRuleSet()
    prepared_documents = {}
    findings = []
    groups = [
        {"category": SimpleNamespace(**bucket["category"]),
         "rules": [SimpleNamespace(**rule) for rule in bucket["rules"]]}
        for bucket in config["groups"]
    ]
    for document in documents:
        source_text = document["text"]
        normalized = normalized_variant(source_text, options["sensitivity"]) if normalization["enabled"] else None
        if normalized:
            normalization["transforms"] = sorted(set(normalization["transforms"]) | set(normalized[2]))
        local = detect(source_text, disabled=disabled)
        if enabled.get("pii", True):
            local.extend(pii(source_text, disabled=disabled))
        prepared = PreparedDocument(source_text)
        if config["references"]:
            prepared_documents[document["id"]] = prepared
        local.extend(evaluate_groups(groups, source_text, normalized=normalized,
                                    available_engines={"keywords", "regex"}, compiled=compiled, prepared=prepared))
        for hit in local:
            hit["document_id"] = document["id"]
            if hit.get("end", 0) > hit.get("start", 0):
                hit.setdefault("original_excerpt", source_text[hit["start"]:hit["end"]])
        findings.extend(local)
    reference_matches = []
    for reference in config["references"]:
        if not enabled.get("reference", True) or "REFERENCE_DOCUMENT" in disabled:
            break
        template = (reference["fingerprint"] or {}).get("document_template")
        if template:
            for attachment in payload["attachments"]:
                if attachment["status"] not in {"ANALYZED", "PARTIAL"} or not attachment["text"].strip():
                    continue
                hit = finding_for_template(attachment["text"], template, reference["id"], attachment["name"])
                if hit:
                    hit["document_id"] = attachment.get("id", attachment["name"])
                    findings.append(hit)
            continue
        for document in documents:
            match = compare(document["text"], reference["text"], reference["fingerprint"])
            if match["exact"] or (match["reference_coverage"] >= 0.3 and len(match["matched_fragments"]) >= 3):
                excerpt = "\n".join(match["matched_fragments"])[:1000]
                reference_matches.append({
                    "reference_id": reference["id"], "confidence": match["reference_coverage"],
                    "excerpt": excerpt, "document_id": document["id"],
                })
                findings.append({
                    "category": "REFERENCE_DOCUMENT", "rule_id": reference["id"], "risk": 75,
                    "confidence": match["reference_coverage"], "start": 0, "end": 0, "excerpt": excerpt,
                    "source": "fingerprint", "version": "shingle5-minhash64-v1", "reason": match["reason"],
                    "status": "ANALYZED", "similarity": match, "document_id": document["id"],
                })
    # Reference evidence cannot satisfy keyword ALL across unrelated documents.
    # Evaluate mixed groups per source as well, preserving the original API.
    if reference_matches:
        for document in documents:
            hits = evaluate_groups(groups, document["text"], references=[r for r in reference_matches
                                   if r["document_id"] == document["id"]],
                                   available_engines={"keywords", "regex", "reference"}, compiled=compiled,
                                   prepared=prepared_documents.get(document["id"]))
            for hit in hits:
                hit["document_id"] = document["id"]
            findings.extend(hits)
    unavailable = not payload.get("ml_available") and any(rule.kind == "ml" for bucket in groups for rule in bucket["rules"])
    return {
        "findings": unique_findings(f for f in findings if f["category"] not in disabled),
        "version": VERSION, "normalization": normalization,
        "engine_errors": [{"engine": "category_ml", "error": "disabled"}] if unavailable else [],
        "skipped_checks": ["ml", "llm"],
    }