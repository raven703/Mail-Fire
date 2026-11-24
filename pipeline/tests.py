from datetime import timedelta
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from pipeline.models import Dispatch, WorkItem
from pipeline.publisher import publish_one
from pipeline.services import StaleAttempt, claim, enqueue, finish, recover


class DeliveryTests(TestCase):
    def test_monitor_page_renders_without_exposing_job_payload(self):
        from identity.models import User

        user = User.objects.create_user("monitor-user", "monitor-password", role="observer")
        self.client.force_login(user)
        session = self.client.session
        session["mice_access_version"] = user.access_version
        session.save()
        enqueue("maintenance.resources", {"sensitive": "not-for-the-page"}, "monitor-test")
        with patch("pipeline.monitoring.app.control.inspect") as inspect:
            inspect.return_value.ping.return_value = {"maintenance@test": {"ok": "pong"}}
            response = self.client.get("/operations/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "maintenance@test")
        self.assertNotContains(response, "not-for-the-page")
        job = WorkItem.objects.get(deduplication_key="monitor-test")
        self.assertEqual(self.client.post(f"/api/jobs/{job.pk}/cancel").status_code, 403)

    def test_atomic_enqueue_and_idempotent_completion(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            enqueue("maintenance.resources", {}, "rolled-back")
            raise RuntimeError()
        self.assertFalse(WorkItem.objects.exists())
        job = enqueue("maintenance.resources", {}, "sample")
        self.assertEqual(enqueue("maintenance.resources", {}, "sample").pk, job.pk)
        running = claim(job.pk, "test-worker")
        self.assertIsNone(claim(job.pk, "duplicate-worker"))
        finish(job.pk, running.token, {"ok": True})
        self.assertIsNone(claim(job.pk, "redelivered-worker"))

    def test_timeout_recovery_fences_old_worker_and_creates_dead_letter(self):
        job = enqueue("maintenance.resources", {}, "timeout", max_attempts=1)
        running = claim(job.pk, "killed-worker")
        WorkItem.objects.filter(pk=job.pk).update(deadline=timezone.now() - timedelta(seconds=1))
        recover()
        job.refresh_from_db()
        self.assertEqual(job.status, WorkItem.Status.DEAD)
        self.assertTrue(Dispatch.objects.filter(job=job, dead_letter=True).exists())
        with self.assertRaises(StaleAttempt):
            finish(job.pk, running.token, {})

    def test_failed_publish_retains_outbox_and_backoff(self):
        enqueue("maintenance.resources", {}, "publish-error")
        with (
            patch("pipeline.publisher.Producer"),
            patch("pipeline.publisher.app.send_task", side_effect=OSError),
        ):
            self.assertFalse(publish_one(None))
        row = Dispatch.objects.get()
        self.assertIsNone(row.published_at)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(row.error, "OSError")
        self.assertGreater(row.available_at, timezone.now())
