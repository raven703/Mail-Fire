"""Persistence-free deterministic analysis using the original MICE algorithms."""

from types import SimpleNamespace


def analyze(payload):
    from app.advanced_detectors import pii
    from app.categories import evaluate_groups
    from app.detectors import VERSION, detect
    from app.document_templates import finding_for_template
    from app.fingerprints import compare
    from app.text_normalizer import DEFAULTS, normalize

    text, config = payload["text"], payload["configuration"]
    options = {**DEFAULTS, **config["settings"].get("normalizer", {})}
    normalization = {"enabled": options["enabled"], "transforms": []}
    if options["enabled"]:
        _, normalization["transforms"] = normalize(text, options["sensitivity"])
    # Normalization is diagnostic, never replace source evidence (master semantics).
    findings = detect(text) + pii(text)
    reference_matches = []
    for reference in config["references"]:
        template = (reference["fingerprint"] or {}).get("document_template")
        if template:
            for attachment in payload["attachments"]:
                if attachment["status"] not in {"ANALYZED", "PARTIAL"} or not attachment["text"].strip():
                    continue
                hit = finding_for_template(attachment["text"], template, reference["id"], attachment["name"])
                if hit:
                    findings.append(hit)
            continue
        match = compare(text, reference["text"], reference["fingerprint"])
        if match["exact"] or (match["reference_coverage"] >= 0.3 and len(match["matched_fragments"]) >= 3):
            excerpt = "\n".join(match["matched_fragments"])[:1000]
            reference_matches.append({
                "reference_id": reference["id"], "confidence": match["reference_coverage"], "excerpt": excerpt,
            })
            findings.append({
                "category": "REFERENCE_DOCUMENT", "rule_id": reference["id"], "risk": 75,
                "confidence": match["reference_coverage"], "start": 0, "end": 0, "excerpt": excerpt,
                "source": "fingerprint", "version": "shingle5-minhash64-v1", "reason": match["reason"],
                "status": "ANALYZED", "similarity": match,
            })
    groups = [
        {"category": SimpleNamespace(**bucket["category"]),
         "rules": [SimpleNamespace(**rule) for rule in bucket["rules"]]}
        for bucket in config["groups"]
    ]
    findings.extend(evaluate_groups(
        groups, text, references=reference_matches,
        ml_scores=payload.get("ml_scores", {}),
        available_engines={"keywords", "regex", "reference"} | ({"ml"} if payload.get("ml_available") else set()),
    ))
    unavailable = not payload.get("ml_available") and any(rule.kind == "ml" for bucket in groups for rule in bucket["rules"])
    return {
        "findings": findings, "version": VERSION, "normalization": normalization,
        "engine_errors": [{"engine": "category_ml", "error": "disabled"}] if unavailable else [],
        "skipped_checks": ["ml", "llm"],
    }