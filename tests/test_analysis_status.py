"""Partial status describes failures of enabled checks, not deliberate opt-outs."""
from app.analysis_status import classify_analysis


def test_disabled_antivirus_is_not_partial():
    assert classify_analysis([], ["DISABLED"], [], []) == ("ANALYZED", ["antivirus"])


def test_disabled_optional_engines_do_not_make_partial():
    status, skipped = classify_analysis(
        [("PARTIAL", {"ocr_required": True})],
        ["DISABLED"], [{"engine": "ml", "error": "Unavailable"}], [],
        antivirus_enabled=False, ml_enabled=False, ocr_enabled=False,
    )
    assert status == "ANALYZED"
    assert skipped == ["antivirus", "ml", "ocr"]


def test_enabled_ocr_failure_remains_partial():
    assert classify_analysis(
        [("PARTIAL", {"ocr_required": True})], ["OK"], [], [],
        ocr_enabled=True,
    )[0] == "PARTIAL"


def test_disabled_ocr_does_not_hide_unrelated_extraction_failure():
    for status, details in [
        ("FAILED", {"error": "ValueError"}),
        ("UNSUPPORTED", {"reason": "unsupported format"}),
        ("PARTIAL", {"error": "page limit"}),
    ]:
        assert classify_analysis(
            [(status, details)], ["DISABLED"], [], [], ocr_enabled=False
        )[0] == "PARTIAL"


def test_enabled_engine_errors_are_partial():
    assert classify_analysis([], ["OK"], [{"engine": "ml", "error": "RuntimeError"}], [])[0] == "PARTIAL"
    assert classify_analysis([], ["OK"], [], ["llm_HTTPStatusError"])[0] == "PARTIAL"
    assert classify_analysis([], ["ERROR"], [], [])[0] == "PARTIAL"


def test_disabled_ml_does_not_suppress_enabled_llm_error():
    assert classify_analysis(
        [], ["DISABLED"], [{"engine": "ml", "error": "RuntimeError"}],
        ["llm_HTTPStatusError"], ml_enabled=False,
    )[0] == "PARTIAL"


def test_clean_active_analyses_are_analyzed():
    assert classify_analysis(
        [("ANALYZED", {})], ["OK", "FOUND"], [], []
    ) == ("ANALYZED", [])
