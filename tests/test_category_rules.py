"""Deterministic category-rule tests without a PostgreSQL service."""

from types import SimpleNamespace

import pytest

from app import categories


def fake_rule(kind, config, ident, *, risk=70, priority=100):
    return SimpleNamespace(
        id=ident,
        kind=kind,
        config=config,
        risk=risk,
        priority=priority,
        title=kind,
    )


def run(monkeypatch, text, rules, *, match_mode="any", refs=(), scores=None, engines=None):
    cat = SimpleNamespace(id="custom-test", name="Test", mode="custom", match_mode=match_mode)
    monkeypatch.setattr(
        categories,
        "rules_for",
        lambda session: {cat.id: {"category": cat, "rules": rules}},
    )
    return categories.custom_findings(
        None,
        text,
        references=refs,
        ml_scores=scores,
        available_engines=engines,
    )


def test_regex_rejects_backtracking_and_accepts_bounded_pattern():
    for pattern in ("(a+)+", "a.*b", "a|b", "a+", "a{33}", "a?", "\\1", ""):
        with pytest.raises(ValueError):
            categories.safe_regex(pattern)
    assert categories.safe_regex(r"DOC-[0-9]{4}").search("Номер DOC-2027")


def test_any_all_and_negative_phrases(monkeypatch):
    rules = [
        fake_rule("keywords", {"phrases": ["прогноз прибыли"]}, "kw"),
        fake_rule("regex", {"pattern": r"DOC-[0-9]{4}", "exclude_phrases": ["публичная версия"]}, "rx"),
    ]
    text = "Письмо содержит прогноз прибыли DOC-2027."
    assert len(run(monkeypatch, text, rules, match_mode="all")) == 2
    assert len(run(monkeypatch, "прогноз прибыли", rules, match_mode="all")) == 0
    assert len(run(monkeypatch, "прогноз прибыли", rules, match_mode="any")) == 1
    assert len(run(monkeypatch, text + " публичная версия", rules, match_mode="all")) == 0


def test_reference_and_ml_rules(monkeypatch):
    rules = [
        fake_rule("reference", {"reference_ids": ["ref-1", "ref-2"], "min_similarity": 0.81}, "ref"),
        fake_rule("ml", {"min_confidence": 0.75}, "ml"),
    ]
    refs = [{"reference_id": "ref-2", "confidence": 0.88, "excerpt": "Financial plan"}]
    scores = {"custom-test": {"matched": True, "confidence": 0.82}}
    result = run(monkeypatch, "Synthetic document", rules, match_mode="all", refs=refs, scores=scores)
    assert {r["rule_id"] for r in result} == {"ref", "ml"}
    assert not run(
        monkeypatch,
        "Synthetic document",
        rules,
        match_mode="all",
        refs=refs,
        scores=scores,
        engines={"keywords", "regex", "reference"},
    )
    assert (
        len(
            run(
                monkeypatch,
                "Synthetic document",
                rules,
                match_mode="any",
                refs=refs,
                scores=scores,
                engines={"keywords", "regex", "reference"},
            )
        )
        == 1
    )


def test_no_rules_or_inactive_rules_do_not_match(monkeypatch):
    assert run(monkeypatch, "Synthetic document", []) == []


def test_empty_engine_set_and_ml_threshold(monkeypatch):
    rules = [fake_rule("keywords", {"phrases": ["секрет"]}, "kw")]
    assert not run(monkeypatch, "секрет", rules, engines=set())
    ml = [fake_rule("ml", {"min_confidence": 0.85}, "ml")]
    assert not run(monkeypatch, "text", ml, scores={"custom-test": {"matched": True, "confidence": 0.84}})
    assert run(monkeypatch, "text", ml, scores={"custom-test": {"matched": True, "confidence": 0.85}})


def test_regex_timeout_preserves_any_keyword(monkeypatch):
    import subprocess

    from app import sandbox

    def unavailable(*args):
        raise subprocess.TimeoutExpired("regex", 2)

    monkeypatch.setattr(sandbox, "local_call", unavailable)
    rules = [
        fake_rule("regex", {"pattern": "a{0,32}a{0,32}b"}, "rx"),
        fake_rule("keywords", {"phrases": ["секрет"]}, "kw"),
    ]
    assert len(run(monkeypatch, "секрет", rules)) == 1
    assert not run(monkeypatch, "секрет", rules, match_mode="all")
