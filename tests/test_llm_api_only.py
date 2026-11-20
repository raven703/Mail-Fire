"""External OpenAI-compatible LLM is opt-in and never contacts a built-in server."""
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Disposable migrated PostgreSQL required")


def test_api_only_llm_routes_selected_categories_with_no_network(monkeypatch):
    import httpx
    from app.db import transaction
    from app.llm_analyzer import analyze
    from app.models import Setting

    with transaction() as session:
        assert not session.get(Setting, "llm_analyzer")
    assert analyze("секретный документ", []) == ([], [])

    calls = []
    def fake_post(self, url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": '{"matches":[{"category":"SECRET","confidence":0.92,"reason":"Тестовый пример"}]}'}}]},
        )
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    try:
        with transaction() as session:
            session.add(Setting(key="llm_analyzer", value={
                "enabled": True, "base_url": "https://example.test/v1",
                "model": "remote-model", "routing": "selected", "categories": ["SECRET"],
                "min_confidence": 0.75, "timeout_seconds": 5, "max_chars": 500,
                "allow_external_content": True,
            }))
        findings, errors = analyze("секретный документ", [])
        assert not errors
        assert len(findings) == 1
        assert findings[0]["category"] == "SECRET"
        assert calls[0][0] == "https://example.test/v1/chat/completions"
        assert calls[0][1]["json"]["model"] == "remote-model"
        assert len(calls) == 1
        with transaction() as session:
            session.get(Setting, "llm_analyzer").value = {
                "enabled": True, "base_url": "https://example.test/v1",
                "model": "remote-model", "routing": "selected", "categories": ["SECRET"],
                "allow_external_content": False,
            }
        assert analyze("секретный документ", [])[0] == []
        assert len(calls) == 1  # Consent removal blocks all HTTP calls.
    finally:
        with transaction() as session:
            row = session.get(Setting, "llm_analyzer")
            if row:
                session.delete(row)
