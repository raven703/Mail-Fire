"""Regression coverage for unified category catalog and controlled ML labels."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Disposable PostgreSQL required")


def test_category_lifecycle_policy_and_ml_labels():
    from fastapi.testclient import TestClient

    from app.db import transaction
    from app.main import app
    from app.models import Category, Policy, TrainingExample

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        assert response.status_code == 200
        headers = {"X-CSRF-Token": response.json()["csrf"]}
        catalog = client.get("/api/categories")
        assert catalog.status_code == 200
        assert any(x["id"] == "CONFIDENTIAL" for x in catalog.json()["items"])
        assert any(x["id"] == "NORMAL" for x in catalog.json()["items"])

        creation = client.post(
            "/api/categories",
            headers=headers,
            json={"name": "Синтетический финансовый прогноз", "group_name": "Финансы",
                  "mode": "keywords", "keywords": ["плановая выручка"]},
        )
        assert creation.status_code == 200, creation.text
        category_id = creation.json()["id"]
        try:
            with transaction() as session:
                from app.categories import keyword_findings

                findings = keyword_findings(session, "Письмо содержит плановая выручка будущего года")
                assert any(x["category"] == category_id for x in findings)

            invalid = client.post(
                "/api/workspace/policies",
                headers=headers,
                json={"name": "Synthetic invalid catalog policy", "categories": ["NONEXISTENT"]},
            )
            assert invalid.status_code == 422

            policy = client.post(
                "/api/workspace/policies",
                headers=headers,
                json={"name": "Synthetic category policy", "categories": [category_id]},
            )
            assert policy.status_code == 200, policy.text
            policy_id = policy.json()["id"]

            invalid_label = client.post(
                "/api/ml/examples", headers=headers,
                json={"text": "Synthetic document used only for testing", "labels": ["NONEXISTENT"], "approved": True},
            )
            assert invalid_label.status_code == 422

            example = client.post(
                "/api/ml/examples", headers=headers,
                json={"text": "Synthetic finance forecast: planned revenue", "labels": [category_id], "approved": True},
            )
            assert example.status_code == 200, example.text
            example_id = example.json()["id"]

            archive = client.post("/api/categories/" + category_id + "/archive", headers=headers)
            assert archive.status_code == 200
            assert not archive.json()["active"]
            assert client.post(
                "/api/workspace/policies", headers=headers,
                json={"name": "Invalid archived", "categories": [category_id]},
            ).status_code == 422
        finally:
            with transaction() as session:
                if "policy_id" in locals():
                    session.delete(session.get(Policy, policy_id))
                if "example_id" in locals():
                    session.delete(session.get(TrainingExample, example_id))
                session.delete(session.get(Category, category_id))


def test_training_example_from_incident():
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.db import transaction
    from app.main import app
    from app.mail import ingest
    from app.models import Content, Incident, MailEvent, Message, Policy, TrainingExample

    data = b"From: analyst@example.com\r\nTo: boss@example.net\r\nSubject: synthetic feedback\r\n\r\n" + b"test " * 20
    with transaction() as session:
        record = ingest(session, data, "test", "feedback-test-" + __import__("uuid").uuid4().hex, "feedback.eml")
        mail = session.get(Message, record.message_id)
        content = Content(normalized_sha=__import__("hashlib").sha256(data + b"feedback").hexdigest(),
                          text="Synthetic financial forecast and planned revenue 2026",
                          analysis={"findings": []})
        session.add(content)
        session.flush()
        mail.content_id = content.id
        policy = Policy(name="Synthetic feedback policy", conditions={"min_risk": 20})
        session.add(policy)
        session.flush()
        event = session.scalar(select(MailEvent).where(MailEvent.message_id == mail.id))
        incident = Incident(event_id=event.id, policy_id=policy.id, findings=[], risk=50)
        session.add(incident)
        session.flush()
        incident_id = incident.id

    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        result = client.post(
            "/api/ml/incidents/" + incident_id + "/example", headers=headers,
            json={"labels": ["NORMAL"], "approved": True},
        )
        assert result.status_code == 200, result.text
        assert result.json()["source_incident_id"] == incident_id
        example_id = result.json()["id"]
        assert client.post(
            "/api/ml/incidents/" + incident_id + "/example", headers=headers,
            json={"labels": ["NORMAL"], "approved": True},
        ).status_code == 409
    with transaction() as session:
        # Only remove test-specific data; queued analysis/evaluation jobs are
        # not executed by these synchronous API tests.
        example = session.get(TrainingExample, example_id)
        session.delete(example)
        session.flush()
        incident = session.get(Incident, incident_id)
        session.delete(incident)
