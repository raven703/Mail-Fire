import os
from datetime import timedelta

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires PostgreSQL")


def test_retention_dry_run_and_legal_hold():
    import uuid

    from test_core import synthetic_mail

    from app.db import transaction
    from app.mail import ingest
    from app.models import Job, Message, now
    from app.retention import cleanup

    with transaction() as db:
        record = ingest(db, synthetic_mail(), "retention-test", str(uuid.uuid4()), "retention.eml")
        message_id = record.message_id
        message = db.get(Message, message_id)
        message.created_at = now() - timedelta(days=500)
        message.legal_hold = True
        for job in db.query(Job).filter(Job.payload["message_id"].astext == message_id):
            job.status = "DONE"
    assert message_id not in cleanup(True)["candidates"]
    with transaction() as db:
        db.get(Message, message_id).legal_hold = False
    assert message_id in cleanup(True)["candidates"]
    assert cleanup(False)["deleted"] >= 1
    with transaction() as db:
        assert db.get(Message, message_id) is None
