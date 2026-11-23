import os

import pytest
from sqlalchemy import func, select

pytestmark = pytest.mark.skipif(
    not os.getenv("MAILFIRE_TEST_DB"),
    reason="Requires migrated disposable PostgreSQL; set MAILFIRE_TEST_DB=1 and DATABASE_URL",
)


def test_ingest_analysis_and_event_identity():
    import uuid

    from test_core import synthetic_mail

    from app.db import transaction
    from app.mail import ingest
    from app.models import Incident, MailEvent, Message
    from app.processing import analyze

    key = uuid.uuid4().hex
    data = synthetic_mail(100)
    with transaction() as db:
        first = ingest(db, data, "test", key, "sample.eml")
        repeated = ingest(db, data, "test", key, "sample.eml")
        assert first.id == repeated.id
        message_id = first.message_id
        second = ingest(db, data, "test", key + "-independent", "sample.eml")
        assert second.message_id == message_id
    analyze(message_id)
    with transaction() as db:
        # Explicitly disabled optional checks do not make successful extraction partial.
        assert db.get(Message, message_id).status == "ANALYZED"
        assert (
            db.scalar(
                select(func.count())
                .select_from(MailEvent)
                .where(MailEvent.source_key.in_([key, key + "-independent"]))
            )
            == 2
        )
        assert db.scalar(select(func.count()).select_from(Incident)) >= 1
