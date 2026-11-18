from datetime import timedelta
from types import SimpleNamespace

from app.background import live
from app.models import now


def test_background_publication_requires_current_live_owner():
    job = SimpleNamespace(status="RUNNING", owner="current", lease_until=now() + timedelta(seconds=60))
    assert live(job, "current")
    assert not live(job, "stale")
    job.status = "CANCELLED"
    assert not live(job, "current")
    job.status = "RUNNING"
    job.lease_until = now() - timedelta(seconds=1)
    assert not live(job, "current")
    job.lease_until = None
    assert not live(job, "current")
