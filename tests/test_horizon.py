"""Offline deterministic Horizon contracts, no weights/GPU/network/database."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from app.categories import evaluate_groups
from app.evidence import evidence_count, unique_findings
from app.horizon import aggregate, analyze_document, chunks, combine, fingerprint, validate


def config(**overrides):
    return {
        "positive_hypotheses": ["secret internal plans"],
        "excluding_hypotheses": [],
        "combine": "single",
        "aggregation": "max",
        "threshold": 0.5,
        **overrides,
    }


def rule(**overrides):
    return NS(id="r", kind="horizon", config=config(), title="Horizon", risk=50, **overrides)


def test_all_frozen_defaults_validate():
    defaults = json.loads((Path(__file__).resolve().parents[1] / "app/horizon_defaults.json").read_text())
    assert len(defaults) == 12
    assert all(c.startswith("pack-ru2-") for c in defaults)
    for value in defaults.values():
        assert validate(value) == value


@pytest.mark.parametrize(
    "changes",
    [
        dict(threshold=float("nan")),
        dict(threshold=0),
        dict(threshold=True),
        dict(positive_hypotheses=[]),
        dict(positive_hypotheses=["abc"] * 11, excluding_hypotheses=["def"]),
        dict(positive_hypotheses=["a" * 601]),
        dict(combine="invented"),
        dict(aggregation="invented"),
        dict(excluding_hypotheses=["not secret"]),
        dict(combine="subtract"),
    ],
)
def test_invalid_config(changes):
    with pytest.raises(ValueError):
        validate(config(**changes))


def test_score_semantics():
    assert combine([0.8, 0.3], "subtract") == 0.5
    assert combine([0.8, 0.3], "product") == pytest.approx(0.56)
    assert combine([0.8, 0.3], "mean") == 0.55
    assert combine([0.8, 0.3], "min") == 0.3
    assert combine([0.8, 0.3], "max") == 0.8
    assert aggregate([0.2, 0.4, 0.8], "top2_mean") == pytest.approx(0.6)
    assert aggregate([0.2, 0.4], "noisy_or") == pytest.approx(0.52)


def test_window_boundaries_and_evidence():
    assert list(chunks("x" * 1700)) == [(0, "x" * 900), (800, "x" * 900)]
    rows, errors = analyze_document("x" * 900 + "y" * 800, [rule()], scorer=lambda p: ([0.2, 0.9], "weights"))
    assert not errors and rows["r"]["start"] == 800 and rows["r"]["end"] == 1700
    assert rows["r"]["matched"] and rows["r"]["model_weights_sha256"] == "weights"
    assert rows["r"]["horizon_config_version"] == fingerprint(config())


def test_limits_failures_and_caching():
    r1, r2 = rule(), NS(**{**vars(rule()), "id": "r2"})
    calls = []

    def scorer(pairs):
        calls.append(len(pairs))
        return [0.7] * len(pairs), "weights"

    rows, errors = analyze_document("hello", [r1, r2], scorer=scorer)
    assert len(rows) == 2 and not errors and calls == [1]
    rows, errors = analyze_document("x" * 50000, [r1], scorer=scorer, budget={"windows": 1, "pairs": 1})
    assert rows and {e["error"] for e in errors} == {"document_character_limit", "message_window_limit"}
    rows, errors = analyze_document("hello", [r1], scorer=scorer, budget={"windows": 1, "pairs": 0})
    assert not rows and errors[0]["error"] == "message_pair_limit"
    rows, errors = analyze_document("hello", [r1], scorer=lambda p: ([float("nan")], "weights"))
    assert not rows and errors


def test_any_all_unavailable_and_independent_methods():
    cat = NS(id="test", mode="custom", match_mode="all")
    hr = rule()
    kw = NS(id="kw", kind="keywords", config={"phrases": ["secret"]}, risk=50, title="keywords")
    bucket = [{"category": cat, "rules": [kw, hr]}]
    assert not evaluate_groups(bucket, "secret", available_engines={"keywords"})
    scores = {
        "horizon:r": {
            "matched": True,
            "confidence": 0.8,
            "excerpt": "secret",
            "start": 0,
            "end": 6,
            "horizon_score": 0.8,
        }
    }
    assert (
        len(evaluate_groups(bucket, "secret", available_engines={"keywords", "horizon"}, ml_scores=scores))
        == 2
    )
    cat.match_mode = "any"
    assert len(evaluate_groups(bucket, "secret", available_engines={"keywords"})) == 1


def test_no_extra_occurrence_or_lost_horizon_metadata():
    native = dict(
        category="test", source="custom-keywords", rule_id="kw", start=2, end=5, risk=50, document_id="body"
    )
    horizon = dict(
        category="test",
        source="custom-horizon",
        rule_id="h",
        start=0,
        end=9,
        risk=50,
        document_id="body",
        horizon_score=0.8,
    )
    rows = unique_findings([native, horizon, horizon])
    assert len(rows) == 2 and any(r.get("horizon_score") == 0.8 for r in rows)
    assert evidence_count(rows) == 1
    assert evidence_count([horizon, {**horizon, "rule_id": "h2"}]) == 1
    assert evidence_count([native, {**native, "start": 7, "end": 8}, horizon]) == 2


def test_all_ml_engines_run_independently(monkeypatch):
    import sys

    from app.ml_runtime import infer_models

    calls = []

    def global_infer(artifact, text):
        calls.append("tfidf")
        return [{"category": "test", "matched": True, "confidence": 0.7}]

    def binary(artifact, text, category, threshold):
        calls.append(artifact)
        if artifact == "broken":
            raise RuntimeError
        return {"category": category, "matched": True, "confidence": 0.8}

    monkeypatch.setitem(sys.modules, "app.ml", NS(infer=global_infer))
    monkeypatch.setitem(sys.modules, "app.ml_engines", NS(infer_binary=binary))
    models = [
        NS(
            id=e,
            engine=e,
            category_id=None if e == "tfidf" else "test",
            metrics={"threshold": 0.5},
            artifact=e,
        )
        for e in ("tfidf", "setfit", "rubert")
    ]
    models.append(
        NS(id="broken", engine="rubert", category_id="test", metrics={"threshold": 0.5}, artifact="broken")
    )
    predictions, errors = infer_models(models, "text")
    assert len(predictions) == 3 and len(errors) == 1
    assert calls == ["tfidf", "setfit", "rubert", "broken"]


def test_multiple_ml_confirmations_do_not_inflate_policy_count():
    first = dict(category='test',document_id='body',source='custom-ml',rule_id='m',start=0,end=0,risk=50)
    second = {**first,'model_id':'other','ml_engine':'rubert'}
    assert evidence_count([first,second]) == 1
    native = {**first,'source':'custom-keywords','start':2,'end':5}
    assert evidence_count([first,second,native]) == 1
