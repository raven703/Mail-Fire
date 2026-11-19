"""Regression: incident evidence is refreshed when semantic findings arrive later.

Uses an isolated PostgreSQL database; never connect this test to production.
"""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Disposable PostgreSQL required")


def test_evaluate_refreshes_evidence_preserves_review_and_does_not_realert(monkeypatch):
    from app.db import transaction
    from app.models import Account, Blob, Comment, Content, Incident, MailEvent, Message, Policy
    from app.processing import evaluate

    token = uuid.uuid4().hex
    digest = token.ljust(64, "0")
    sent = []
    monkeypatch.setattr("app.integrations.enqueue", lambda session, incident: sent.append(incident.id))
    try:
        with transaction() as db:
            blob = Blob(sha=digest, data=b"synthetic eml", size=13)
            content = Content(
                normalized_sha=digest,
                text="synthetic content",
                version="test",
                analysis={"findings": [{"category": "SECRET", "risk": 45, "source": "regex"}]},
            )
            policy = Policy(
                name="Synthetic semantic reanalysis " + token,
                enabled=True,
                shadow=False,
                priority=9999,
                conditions={"categories": ["SECRET"], "min_risk": 40, "min_count": 1},
            )
            db.add_all([blob, content, policy])
            db.flush()
            mail = Message(
                original_sha=digest,
                format="eml",
                content_id=content.id,
                sender="example@external.test",
                subject="Synthetic",
                recipients=["other@external.test"],
            )
            db.add(mail)
            db.flush()
            event = MailEvent(message_id=mail.id, source="web", source_key="synthetic:" + token)
            db.add(event)
            db.flush()
            event_id, content_id, policy_id, mail_id = event.id, content.id, policy.id, mail.id
        evaluate(event_id)
        with transaction() as db:
            first = db.query(Incident).filter_by(event_id=event_id, policy_id=policy_id).one()
            assert first.risk == 45
            first.status = "REVIEW"
            account = db.query(Account).filter_by(username="admin").one()
            first.assignee = account.id
            assignee_id = account.id
            db.add(Comment(incident_id=first.id, account_id=account.id, text="Synthetic review note"))
            first_id = first.id
            db.get(Content, content_id).analysis = {
                "findings": [
                    {"category": "SECRET", "risk": 45, "source": "regex"},
                    {"category": "SECRET", "risk": 90, "source": "semantic"},
                ]
            }
        evaluate(event_id)
        with transaction() as db:
            incidents = db.query(Incident).filter_by(event_id=event_id, policy_id=policy_id).all()
            assert len(incidents) == 1
            incident = incidents[0]
            assert incident.id == first_id
            assert incident.risk == 90
            assert len(incident.findings) == 2
            assert incident.status == "REVIEW"
            assert incident.assignee == assignee_id
            assert db.query(Comment).filter_by(incident_id=first_id).one().text == "Synthetic review note"
        assert sent.count(first_id) == 1
    finally:
        # Cleanup in FK order so this test never modifies shared fixtures.
        with transaction() as db:
            if "event_id" in locals():
                if "first_id" in locals():
                    db.query(Comment).filter_by(incident_id=first_id).delete()
                db.query(Incident).filter_by(event_id=event_id).delete()
                db.query(MailEvent).filter_by(id=event_id).delete()
            if "mail_id" in locals():
                db.query(Message).filter_by(id=mail_id).delete()
            if "content_id" in locals():
                db.query(Content).filter_by(id=content_id).delete()
            if "policy_id" in locals():
                db.query(Policy).filter_by(id=policy_id).delete()
            db.query(Blob).filter_by(sha=digest).delete()
