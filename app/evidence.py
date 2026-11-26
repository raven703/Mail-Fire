"""Source coordinates, conservative normalization and unique evidence identities."""

import re
import unicodedata

from app.text_normalizer import SEPARATED, TOKEN, ZERO_WIDTH, normalize

from app.category_catalog import LEGACY_ALIASES as ALIASES


def normalization_safe_regex(pattern):
    # Identifier, secret and ASCII/code expressions run on original text only.
    # Only literal Cyrillic patterns (without regex operators) are safe here.
    return bool(re.search("[А-Яа-яЁё]", pattern)) and not re.search(r"[^А-Яа-яЁё\s-]", pattern)


def normalized_variant(text, sensitivity):
    if sensitivity not in {"low", "medium", "high"}:
        raise ValueError("Unknown sensitivity")
    spans = []
    chars = []
    transforms = []
    for match in re.finditer(r".[\u0300-\u036f]*", text, re.DOTALL):
        value = unicodedata.normalize("NFKC", match.group())
        if value != match.group() and "unicode_nfkc" not in transforms:
            transforms.append("unicode_nfkc")
        for char in value:
            if ZERO_WIDTH.fullmatch(char):
                if "invisible_characters" not in transforms:
                    transforms.append("invisible_characters")
                continue
            chars.append(char)
            spans.append((match.start(), match.end()))
    variant = "".join(chars)
    if sensitivity in {"medium", "high"}:
        def restore(match):
            word = match.group()
            # No conversion of digits in identifiers/alphanumeric part numbers.
            if not re.search("[А-Яа-яЁё]", word) or sum(c.isdigit() for c in word) > 1:
                return word
            return normalize(word, sensitivity)[0]
        cleaned = TOKEN.sub(restore, variant)
        if cleaned != variant:
            transforms.append("mixed_script_or_digits")
        variant = cleaned
    if sensitivity == "high":
        removed = set()
        for match in SEPARATED.finditer(variant):
            removed.update(i for i in range(match.start(), match.end()) if re.match(r"[.·_\-\s]", variant[i]))
        if removed:
            transforms.append("separated_letters")
            spans = [span for i, span in enumerate(spans) if i not in removed]
            variant = "".join(c for i, c in enumerate(variant) if i not in removed)
    return variant, spans, transforms


def map_finding(hit, original, spans, transforms):
    hit = dict(hit)
    start, end = hit["start"], hit["end"]
    if end <= start or end > len(spans):
        raise ValueError("Invalid normalized evidence coordinates")
    hit["normalized_excerpt"] = hit.get("original_excerpt", hit.get("excerpt", ""))
    hit["start"], hit["end"] = spans[start][0], spans[end-1][1]
    hit["original_excerpt"] = original[hit["start"]:hit["end"]]
    hit["excerpt"] = original[max(0, hit["start"]-40):hit["end"]+40]
    hit["normalization"] = list(transforms)
    return hit


def unique_findings(findings):
    """Merge the same evidence, retaining all rule provenance and highest risk.

    Different categories retain their evidence for ANY/ALL. policy_matches
    counts an exact shared span only once across categories.
    """
    result = []
    indexed = {}
    for item in findings:
        hit = dict(item)
        hit["category"] = ALIASES.get(hit["category"], hit["category"])
        start, end = hit.get("start", 0), hit.get("end", 0)
        if end > start:
            key = (hit.get("document_id", "message"), hit["category"], start, end)
        else:
            key = (hit.get("document_id", "message"), hit["category"], hit.get("source"),
                   hit.get("rule_id"), hit.get("filename"), hit.get("excerpt"))
        if key not in indexed:
            if end > start:
                # Different rules can describe the same minimal evidence with
                # a wider context span. Containment is not an independent hit.
                for prior_key, prior in indexed.items():
                    a, b = prior.get("start", 0), prior.get("end", 0)
                    if (b > a and prior.get("document_id", "message") == hit.get("document_id", "message")
                            and prior["category"] == hit["category"]
                            and ((a <= start and end <= b) or (start <= a and b <= end))):
                        key = prior_key
                        break
            if key in indexed:
                prior = indexed[key]
            else:
                indexed[key] = hit
                result.append(hit)
                continue
        prior = indexed[key]
        evidence = prior.setdefault("supporting_rules", [
            {k: prior[k] for k in ("rule_id", "risk", "match_score", "source", "normalization") if k in prior}
        ])
        detail = {k: hit[k] for k in ("rule_id", "risk", "match_score", "source", "normalization") if k in hit}
        if detail not in evidence:
            evidence.append(detail)
        if hit.get("context_matches"):
            contexts = prior.setdefault("context_matches", [])
            for context in hit["context_matches"]:
                if context not in contexts:
                    contexts.append(context)
        prior["risk"] = max(prior["risk"], hit["risk"])
    return result


def evidence_count(findings):
    return len({(f.get("document_id", "message"), f["start"], f["end"])
                if f.get("end", 0) > f.get("start", 0) else
                (f.get("document_id", "message"), f["category"], f.get("source"),
                 f.get("rule_id"), f.get("filename"), f.get("excerpt")) for f in findings})