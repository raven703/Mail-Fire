import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires disposable PostgreSQL")


def test_login_import_view_and_csrf():
    from fastapi.testclient import TestClient
    from test_core import synthetic_mail

    from app.api import app

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/me").status_code == 401
        assert client.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        response = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        assert response.status_code == 200
        csrf = response.json()["csrf"]
        assert client.post("/api/import", files={"files": ("test.eml", synthetic_mail())}).status_code == 403
        result = client.post(
            "/api/import", headers={"X-CSRF-Token": csrf}, files={"files": ("test.eml", synthetic_mail())}
        )
        assert result.status_code == 200
        message_id = result.json()[0]["message_id"]
        assert client.get("/api/messages/" + message_id).status_code == 200
        assert client.get("/api/messages/" + message_id + "/original").content
        assert client.get("/api/monitor").json()["messages"] >= 1
        assert client.post("/api/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
        assert client.get("/api/me").status_code == 401
