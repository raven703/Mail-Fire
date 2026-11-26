"""Evaluate independently configurable rule sets for user-defined categories.

A category fires when ANY/ALL of its enabled detection rules match. A disabled
or missing engine does not silently count as a negative match.
"""

import re
import subprocess

MAX_FINDINGS = 200
MAX_REGEX_TEXT = 100_000




def safe_regex(pattern):
    """A deliberately narrow linear-ish regex subset for untrusted admin patterns.

    No parentheses, alternation, backreferences, lookarounds or wildcards.
    Max 120 characters, bounded {m,n} repeats only, at most 20 repetition
    tokens, no quantifiers on unbounded tokens. Not a general regex engine.
    """
    if not 1 <= len(pattern) <= 120:
        raise ValueError("Длина Regex: 1–120 символов")
    if any(c in pattern for c in "()|*+"):
        raise ValueError("Regex: группы, альтернативы и неограниченные повторы запрещены")
    if re.search(r"(?<!\\)\?", pattern):
        raise ValueError("Regex: оператор ? запрещён")
    # Reject escaped backrefs, unknown escapes, and explicit dot wildcards.
    if re.search(r"\\(?![dDwWsSbBAZ\\.\-])", pattern):
        raise ValueError("Regex: разрешены только безопасные классы и границы")
    if re.search(r"(?<!\\)\.", pattern):
        raise ValueError("Regex: универсальный символ . запрещён")
    repeats = re.findall(r"\{(\d+)(?:,(\d+))?\}", pattern)
    if len(repeats) > 20:
        raise ValueError("Regex: слишком много повторов")
    for minimum, maximum in repeats:
        hi = int(maximum or minimum)
        if hi > 32 or int(minimum) > hi:
            raise ValueError("Regex: повтор должен быть ограничен 32")
    # Reject malformed quantifiers and nested character classes.
    if pattern.count("[") != pattern.count("]"):
        raise ValueError("Regex: некорректный класс символов")
    clean = re.sub(r"\{\d+(?:,\d+)?\}", "", pattern)
    if any(c in clean for c in "{}"):
        raise ValueError("Regex: некорректные повторы")
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError("Некорректное регулярное выражение") from exc




def _make_finding(category, rule, text, source, *, confidence=None):
    from app.advanced_detectors import finding

    found = finding(
        category.id,
        source,
        text[:500],
        risk=rule.risk,
        reason="Совпадение с пользовательским правилом: " + (rule.title or rule.kind),
    )
    found["rule_id"] = rule.id
    found["rule_version"] = getattr(rule, "version", "unspecified")
    found["historical_rule"] = {"id": rule.id, "kind": rule.kind, "title": rule.title,
                                "risk": rule.risk, "config": rule.config,
                                "version": found["rule_version"]}
    found["historical_category"] = getattr(category, "name", category.id)
    found["confidence"] = confidence
    return found


def _hits(rule, category, text, matches, ml_scores, *, prepared=None, compiled=None):
    config = rule.config or {}
    if rule.kind == "keywords":
        from app.text_match import search

        hits = search(
            text,
            mode=config.get("match_type", "substring"),
            phrases=config.get("phrases", []),
            terms=config.get("terms", []),
            window=config.get("window", 12),
            ordered=config.get("ordered", False),
            min_score=config.get("min_score", 1),
            exclude_phrases=config.get("exclude_phrases", []),
            prepared=prepared, compiled=compiled.keywords(rule) if compiled is not None else None,
        )
        output = []
        for start, end, score, confidence in hits:
            found = _make_finding(
                category, rule, text[max(0, start-40):min(len(text),end+40)], "custom-keywords",
                confidence=confidence if config.get("match_type") == "flexible" else None
            )
            found.update(start=start, end=end, original_excerpt=text[start:end], match_score=score)
            output.append(found)
        return output
    if rule.kind == "regex":
        from app.sandbox import local_call

        output = []
        try:
            spans = local_call("regex", text[:MAX_REGEX_TEXT].encode(), config["pattern"])
        except (RuntimeError, ValueError, subprocess.TimeoutExpired):
            return []
        for start, end in spans:
            from app.text_match import excluded
            if excluded(text, start, end, config.get("exclude_phrases", [])):
                continue
            output.append(
                _make_finding(
                    category, rule, text[max(0, start - 40) : end + 40], "custom-regex"
                )
            )
            output[-1].update(start=start, end=end, original_excerpt=text[start:end])
            if len(output) >= 10:
                break
        return output
    if rule.kind == "reference":
        result = []
        ids = set(config.get("reference_ids", []))
        threshold = float(config.get("min_similarity", 0.8))
        for item in matches:
            if item["reference_id"] in ids and item["confidence"] >= threshold:
                result.append(
                    _make_finding(
                        category, rule, item["excerpt"], "custom-reference", confidence=item["confidence"]
                    )
                )
        return result
    if rule.kind == "ml":
        prediction = ml_scores.get(category.id)
        if (
            prediction
            and prediction["matched"]
            and prediction["confidence"] >= float(config.get("min_confidence", 0.7))
        ):
            return [_make_finding(category, rule, "", "custom-ml", confidence=prediction["confidence"])]
        return []
    return []


def custom_findings(session, text, *, references=(), ml_scores=None, available_engines=None):
    """Evaluate category logic once, after all evidence sources are collected.

    references items: reference_id, confidence, excerpt.
    An unknown/unavailable engine suppresses ALL-mode categories (fail-closed
    for detecting, not proof that text is safe).
    """
    return evaluate_groups(
        rules_for(session).values(), text, references=references,
        ml_scores=ml_scores, available_engines=available_engines,
    )


def evaluate_groups(groups, text, *, references=(), ml_scores=None, available_engines=None, normalized=None, compiled=None, prepared=None):
    """Persistence-independent rule evaluation shared by native Django and reference app."""
    from app.text_match import PreparedDocument, CompiledRuleSet
    prepared = prepared if prepared is not None else PreparedDocument(text)
    variant_prepared = PreparedDocument(normalized[0]) if normalized else None
    compiled = compiled if compiled is not None else CompiledRuleSet()
    result = []
    ml_scores = ml_scores or {}
    if available_engines is None:
        available_engines = {"keywords", "regex", "reference", "ml"}
    for bucket in groups:
        category, rules = bucket["category"], bucket["rules"]
        if not getattr(category, "active", True) or category.mode in {"builtin", "label"}:
            continue
        hits = []
        all_good = True
        for rule in rules:
            if not getattr(rule, "enabled", True) or getattr(rule, "deleted_at", None):
                continue
            if rule.kind not in available_engines:
                all_good = False
                continue
            rule_hits = _hits(rule, category, text, references, ml_scores, prepared=prepared, compiled=compiled)
            if normalized and rule.kind in {"keywords", "regex"}:
                from app.evidence import map_finding, normalization_safe_regex
                variant, spans, transforms = normalized
                if rule.kind == "keywords" or normalization_safe_regex(rule.config.get("pattern", "")):
                    for hit in _hits(rule, category, variant, references, ml_scores, prepared=variant_prepared, compiled=compiled):
                        mapped = map_finding(hit, text, spans, transforms)
                        from app.text_match import excluded
                        if not excluded(text, mapped["start"], mapped["end"], rule.config.get("exclude_phrases", [])):
                            rule_hits.append(mapped)
            if not rule_hits:
                all_good = False
            hits.extend(rule_hits)
        if hits and (category.match_mode == "any" or all_good):
            result.extend(hits[:30])
        if len(result) >= MAX_FINDINGS:
            return result[:MAX_FINDINGS]
    return result


def annotate_builtin_context(groups, text, native, *, prepared=None, compiled=None, normalized=None):
    """Supplement native text findings; never create or upgrade a native hit.

    The supplemental match belongs to the same MIME document. Its configured
    risk, if any, is not a policy threshold and its span is not new evidence.
    Invalid/suspected native identifiers retain their native verification.
    """
    from app.category_catalog import CONTEXT_CATEGORIES, CONTEXT_KINDS, CONTEXT_MARKER
    from app.evidence import ALIASES
    by_category = {}
    for hit in native:
        key = ALIASES.get(hit["category"], hit["category"])
        by_category.setdefault(key, []).append(hit)
    if not by_category:
        return
    from app.text_match import PreparedDocument
    variant_prepared = None
    for bucket in groups:
        category = bucket["category"]
        if category.mode != "builtin" or category.id not in CONTEXT_CATEGORIES:
            continue
        base = by_category.get(category.id, [])
        if not base or not getattr(category, "active", True):
            continue
        for rule in bucket["rules"]:
            if (not getattr(rule, "enabled", True) or getattr(rule, "deleted_at", None)
                    or rule.kind not in CONTEXT_KINDS or (rule.config or {}).get(CONTEXT_MARKER) is not True):
                continue
            matches = _hits(rule, category, text, (), {}, prepared=prepared, compiled=compiled)
            if normalized and rule.kind in CONTEXT_KINDS:
                from app.evidence import map_finding, normalization_safe_regex
                from app.text_match import excluded
                if rule.kind == "keywords" or normalization_safe_regex(rule.config.get("pattern", "")):
                    variant, spans, transforms = normalized
                    if variant_prepared is None:
                        variant_prepared = PreparedDocument(variant)
                    for item in _hits(rule, category, variant, (), {}, prepared=variant_prepared, compiled=compiled):
                        mapped = map_finding(item, text, spans, transforms)
                        if not excluded(text, mapped["start"], mapped["end"], rule.config.get("exclude_phrases", [])):
                            matches.append(mapped)
            # Attach only matches that overlap the native occurrence. Context
            # elsewhere in the same document must not label unrelated numbers.
            for hit in base:
                a, b = hit.get("start", 0), hit.get("end", 0)
                if b <= a:
                    continue
                entries = hit.get("context_matches", [])
                for match in matches[:30]:
                    if max(a, match.get("start", 0)) >= min(b, match.get("end", 0)):
                        continue
                    entry = {k: match[k] for k in ("rule_id", "rule_version", "historical_rule",
                             "source", "start", "end", "excerpt", "original_excerpt",
                             "match_score", "normalization") if k in match}
                    if entry not in entries and len(entries) < 30:
                        entries.append(entry)
                if entries:
                    hit["context_matches"] = entries
