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
            json={
                "name": "Синтетический финансовый прогноз",
                "group_name": "Финансы",
                "match_mode": "any",
                "rules": [
                    {"kind": "keywords", "title": "Фраза выручка", "phrases": ["плановая выручка"]},
                    {"kind": "regex", "title": "Код проекта", "pattern": "FNC-[0-9]{4}"},
                ],
            },
        )
        assert creation.status_code == 200, creation.text
        category_id = creation.json()["id"]
        try:
            with transaction() as session:
                from app.categories import custom_findings

                one = custom_findings(session, "Письмо содержит плановая выручка будущего года")
                assert any(x["category"] == category_id for x in one)
                regex = custom_findings(session, "Проект FNC-2027 успешно создан")
                assert any(x["source"] == "custom-regex" for x in regex)
                miss = custom_findings(session, "Несвязанная заметка")
                assert not any(x["category"] == category_id for x in miss)

            body_all = {
                "name": "Синтетический финансовый прогноз",
                "group_name": "Финансы",
                "match_mode": "all",
                "rules": [
                    {"kind": "keywords", "phrases": ["плановая выручка"]},
                    {"kind": "regex", "pattern": "FNC-[0-9]{4}"},
                ],
            }
            updated = client.put("/api/categories/" + category_id, headers=headers, json=body_all)
            assert updated.status_code == 200, updated.text
            with transaction() as session:
                from app.categories import custom_findings

                only_one = custom_findings(session, "плановая выручка")
                assert not any(x["category"] == category_id for x in only_one)
                both = custom_findings(session, "плановая выручка FNC-2027")
                assert len([x for x in both if x["category"] == category_id]) == 2

            bad_pattern = client.put(
                "/api/categories/" + category_id,
                headers=headers,
                json={
                    "name": "Синтетический финансовый прогноз",
                    "rules": [{"kind": "regex", "pattern": "(a+)+"}],
                },
            )
            assert bad_pattern.status_code == 422

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
                "/api/ml/examples",
                headers=headers,
                json={
                    "text": "Synthetic document used only for testing",
                    "labels": ["NONEXISTENT"],
                    "approved": True,
                },
            )
            assert invalid_label.status_code == 422

            example = client.post(
                "/api/ml/examples",
                headers=headers,
                json={
                    "text": "Synthetic finance forecast: planned revenue",
                    "labels": [category_id],
                    "approved": True,
                },
            )
            assert example.status_code == 200, example.text
            example_id = example.json()["id"]

            archive = client.post("/api/categories/" + category_id + "/archive", headers=headers)
            assert archive.status_code == 200
            assert not archive.json()["active"]
            assert (
                client.post(
                    "/api/workspace/policies",
                    headers=headers,
                    json={"name": "Invalid archived", "categories": [category_id]},
                ).status_code
                == 422
            )
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
    from app.mail import ingest
    from app.main import app
    from app.models import (
        Blob,
        Content,
        ImportRecord,
        Incident,
        Job,
        MailEvent,
        Message,
        Policy,
        TrainingExample,
    )

    nonce = __import__("uuid").uuid4().hex
    data = (
        b"From: analyst@example.com\r\nTo: boss@example.net\r\n"
        + ("Message-ID: <" + nonce + "@example.test>\r\n").encode()
        + b"Subject: synthetic feedback\r\n\r\n"
        + b"test " * 20
    )
    with transaction() as session:
        record = ingest(
            session, data, "test", "feedback-test-" + __import__("uuid").uuid4().hex, "feedback.eml"
        )
        mail = session.get(Message, record.message_id)
        content = Content(
            normalized_sha=__import__("hashlib").sha256(data + b"feedback").hexdigest(),
            text="Synthetic financial forecast and planned revenue 2026",
            analysis={"findings": []},
        )
        session.add(content)
        session.flush()
        mail.content_id = content.id
        policy = Policy(name="Synthetic feedback policy", conditions={"min_risk": 20})
        session.add(policy)
        session.flush()
        event = session.scalar(select(MailEvent).where(MailEvent.message_id == mail.id))
        incident = Incident(event_id=event.id, message_id=mail.id, policy_id=policy.id, findings=[], risk=50)
        session.add(incident)
        session.flush()
        incident_id = incident.id

    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        result = client.post(
            "/api/ml/incidents/" + incident_id + "/example",
            headers=headers,
            json={"labels": ["NORMAL"], "approved": True},
        )
        assert result.status_code == 200, result.text
        assert result.json()["source_incident_id"] == incident_id
        example_id = result.json()["id"]
        assert (
            client.post(
                "/api/ml/incidents/" + incident_id + "/example",
                headers=headers,
                json={"labels": ["NORMAL"], "approved": True},
            ).status_code
            == 409
        )
    with transaction() as session:
        from sqlalchemy import delete

        event_ids = select(MailEvent.id).where(MailEvent.message_id == mail.id)
        session.execute(delete(TrainingExample).where(TrainingExample.id == example_id))
        session.execute(delete(Incident).where(Incident.id == incident_id))
        session.execute(
            delete(Job).where(
                (Job.payload["message_id"].astext == mail.id) | Job.payload["event_id"].astext.in_(event_ids)
            )
        )
        session.execute(delete(ImportRecord).where(ImportRecord.message_id == mail.id))
        session.execute(delete(MailEvent).where(MailEvent.message_id == mail.id))
        session.execute(delete(Message).where(Message.id == mail.id))
        session.execute(delete(Content).where(Content.id == content.id))
        session.execute(delete(Policy).where(Policy.id == policy.id))
        session.execute(delete(Blob).where(Blob.sha == mail.original_sha))
