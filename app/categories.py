"""Evaluate independently configurable rule sets for user-defined categories.

A category fires when ANY/ALL of its enabled detection rules match. A disabled
or missing engine does not silently count as a negative match.
"""
import re

from sqlalchemy import select

from app.models import Category, CategoryRule

MAX_FINDINGS = 200
MAX_REGEX_TEXT = 100_000


def available_categories(session, ids, *, allow_label=True):
    values = set(ids)
    if not values:
        return True
    rows = session.scalars(select(Category).where(Category.id.in_(values), Category.active.is_(True)))
    found = {r.id for r in rows if allow_label or r.mode != "label"}
    return found == values


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


def rules_for(session):
    rows = session.execute(
        select(CategoryRule, Category)
        .join(Category, Category.id == CategoryRule.category_id)
        .where(Category.active.is_(True), CategoryRule.enabled.is_(True))
        .order_by(CategoryRule.created_at, CategoryRule.id)
    )
    groups = {}
    for rule, category in rows:
        groups.setdefault(category.id, {"category": category, "rules": []})["rules"].append(rule)
    return groups


def _make_finding(category, rule, text, source, *, confidence=None):
    from app.advanced_detectors import finding

    found = finding(
        category.id, source, text[:500], risk=rule.risk,
        reason="Совпадение с пользовательским правилом: " + (rule.title or rule.kind),
    )
    found["rule_id"] = rule.id
    found["confidence"] = confidence
    return found


def _hits(rule, category, text, matches, ml_scores):
    config = rule.config or {}
    if rule.kind == "keywords":
        lower = text.lower()
        result = []
        for phrase in config.get("phrases", [])[:30]:
            pos = lower.find(phrase.lower())
            if pos >= 0:
                result.append(_make_finding(category, rule, text[max(0, pos - 40): pos + len(phrase) + 40], "custom-keywords"))
        return result
    if rule.kind == "regex":
        pattern = safe_regex(config["pattern"])
        output = []
        for match in pattern.finditer(text[:MAX_REGEX_TEXT]):
            output.append(_make_finding(category, rule, text[max(0, match.start() - 40):match.end() + 40], "custom-regex"))
            if len(output) >= 10:
                break
        return output
    if rule.kind == "reference":
        result = []
        ids = set(config.get("reference_ids", []))
        threshold = float(config.get("min_similarity", 0.8))
        for item in matches:
            if item["reference_id"] in ids and item["confidence"] >= threshold:
                result.append(_make_finding(category, rule, item["excerpt"], "custom-reference", confidence=item["confidence"]))
        return result
    if rule.kind == "ml":
        prediction = ml_scores.get(category.id)
        if prediction and prediction["matched"] and prediction["confidence"] >= float(config.get("min_confidence", 0.7)):
            return [_make_finding(category, rule, "", "custom-ml", confidence=prediction["confidence"])]
        return []
    return []


def custom_findings(session, text, *, references=(), ml_scores=None, available_engines=None):
    """Evaluate category logic once, after all evidence sources are collected.

    references items: reference_id, confidence, excerpt.
    An unknown/unavailable engine suppresses ALL-mode categories (fail-closed
    for detecting, not proof that text is safe).
    """
    result = []
    ml_scores = ml_scores or {}
    available_engines = available_engines or {"keywords", "regex", "reference", "ml"}
    for bucket in rules_for(session).values():
        category, rules = bucket["category"], bucket["rules"]
        if category.mode in {"builtin", "label"}:
            continue
        hits = []
        all_good = True
        for rule in rules:
            if rule.kind not in available_engines:
                all_good = False
                continue
            rule_hits = _hits(rule, category, text, references, ml_scores)
            if not rule_hits:
                all_good = False
            hits.extend(rule_hits)
        if hits and (category.match_mode == "any" or all_good):
            result.extend(hits[:30])
        if len(result) >= MAX_FINDINGS:
            return result[:MAX_FINDINGS]
    return result
