import os
from datetime import timedelta

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires PostgreSQL")


def test_lease_recovery_and_old_owner_fencing():
    from app.db import transaction
    from app.models import Job, now
    from app.worker import claim, complete, heartbeat

    with transaction() as db:
        job = Job(kind="test", payload={}, priority=-100)
        db.add(job)
        db.flush()
        job_id = job.id
    assert claim("first-owner")[0] == job_id
    assert heartbeat(job_id, "first-owner")
    assert not heartbeat(job_id, "wrong-owner")
    with transaction() as db:
        db.get(Job, job_id).lease_until = now() - timedelta(seconds=5)
    assert not complete(job_id, "first-owner")
    assert claim("second-owner")[0] == job_id
    assert not heartbeat(job_id, "first-owner")
    assert not complete(job_id, "first-owner")
    assert complete(job_id, "second-owner")
    with transaction() as db:
        assert db.get(Job, job_id).attempts == 2
        assert db.get(Job, job_id).status == "DONE"
