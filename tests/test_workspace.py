import os
from datetime import UTC, datetime, timedelta

import pytest

from app.workspace_api import period, risk_filter, severity


def test_period_validation_and_severity():
    from fastapi import HTTPException

    end = datetime.now(UTC)
    begin, finish = period(end - timedelta(hours=24), end)
    assert finish - begin == timedelta(hours=24)
    assert begin.tzinfo is None
    with pytest.raises(HTTPException):
        period(end, end)
    with pytest.raises(HTTPException):
        period(datetime.now(), end)
    assert [severity(r) for r in [0, 39, 40, 69, 70, 100]] == [
        "LOW",
        "LOW",
        "MEDIUM",
        "MEDIUM",
        "HIGH",
        "HIGH",
    ]
    with pytest.raises(HTTPException):
        risk_filter(None, "INVALID")


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires disposable PostgreSQL")
def test_workspace_api():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/workspace/overview").status_code == 401
        login = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        assert login.status_code == 200
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        for path in ["overview", "messages", "incidents", "analysts", "preferences"]:
            r = client.get("/api/workspace/" + path)
            assert r.status_code == 200, r.text
        for params in [
            {"q": "@example"},
            {"q": "финансовый отчет"},
            {"incidents": "yes", "severity": "HIGH"},
            {"attachments": "no"},
            {"sort": "risk", "order": "asc"},
        ]:
            r = client.get("/api/workspace/messages", params=params)
            assert r.status_code == 200, r.text
        assert client.get("/api/workspace/messages?sort=DROP").status_code == 422
        assert (
            client.get(
                "/api/workspace/messages?start=2026-01-01T00:00:00&end=2026-01-02T00:00:00"
            ).status_code
            == 422
        )
        assert client.put("/api/workspace/preferences", json={"theme": "dark"}).status_code == 403
        assert (
            client.put("/api/workspace/preferences", json={"theme": "dark"}, headers=headers).status_code
            == 200
        )
        assert client.get("/api/workspace/preferences").json()["theme"] == "dark"
        body = {"name": "Synthetic workspace policy", "shadow": True, "categories": ["CONFIDENTIAL"]}
        created = client.post("/api/workspace/policies", json=body, headers=headers)
        assert created.status_code == 200, created.text
        policy_id = created.json()["id"]
        body["name"] = "Synthetic workspace policy updated"
        updated = client.put("/api/workspace/policies/" + policy_id, json=body, headers=headers)
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        assert len(client.get(f"/api/workspace/policies/{policy_id}/history").json()["items"]) == 2
