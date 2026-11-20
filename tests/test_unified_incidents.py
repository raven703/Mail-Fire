"""End-to-end DB regression for one incident with multiple policy matches."""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires disposable migrated PostgreSQL")


def test_two_policies_one_message_one_incident_and_delete_preserves_history(monkeypatch):
    from app.db import transaction
    from app.models import Blob, Content, Incident, MailEvent, Message, Policy
    from app.processing import evaluate

    token = uuid.uuid4().hex
    digest = token.ljust(64, "0")
    sent = []
    monkeypatch.setattr("app.integrations.enqueue", lambda session, incident: sent.append(incident.id))
    with transaction() as db:
        blob = Blob(sha=digest, data=b"test", size=4)
        content = Content(normalized_sha=digest, text="sample",
                          analysis={"findings":[{"category":"SECRET","risk":85,"source":"text"}]})
        p1 = Policy(name="test " + token + "a", conditions={"categories":["SECRET"], "min_risk":40})
        p2 = Policy(name="test " + token + "b", conditions={"categories":["SECRET"], "min_risk":70})
        db.add_all([blob,content,p1,p2]);db.flush()
        mail = Message(original_sha=digest,format="eml",content_id=content.id,sender="a@example.test",
                       recipients=["b@example.test"])
        db.add(mail);db.flush()
        e1 = MailEvent(message_id=mail.id,source="web",source_key="test1:"+token)
        e2 = MailEvent(message_id=mail.id,source="web",source_key="test2:"+token)
        db.add_all([e1,e2]);db.flush()
        mid, pid1, pid2, eid1, eid2 = mail.id,p1.id,p2.id,e1.id,e2.id
    try:
        evaluate(eid1)
        evaluate(eid2)
        with transaction() as db:
            rows = db.query(Incident).filter_by(message_id=mid).all()
            assert len(rows)==1
            incident=rows[0]
            assert {h["policy_id"] for h in incident.policy_hits} >= {pid1,pid2}
            assert incident.risk == 85
            iid=incident.id
            incident.status="REVIEW"
            db.get(Policy,pid1).enabled=False
        evaluate(eid2)
        with transaction() as db:
            incident = db.get(Incident,iid)
            assert incident.status == "REVIEW"
            assert len([h for h in incident.policy_hits if h["policy_id"] == pid1]) == 1
            assert len([h for h in incident.policy_hits if h["policy_id"] == pid2]) == 1
            assert sent.count(iid)==1
    finally:
        with transaction() as db:
            db.query(Incident).filter_by(message_id=mid).delete()
            db.query(MailEvent).filter(MailEvent.id.in_([eid1,eid2])).delete(synchronize_session=False)
            db.query(Message).filter_by(id=mid).delete()
            db.query(Content).filter_by(normalized_sha=digest).delete()
            db.query(Policy).filter(Policy.id.in_([pid1,pid2])).delete(synchronize_session=False)
            db.query(Blob).filter_by(sha=digest).delete()
