"""Focused PR36 integration regressions; isolated Django test database only."""
import hashlib
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from identity.models import User
from pipeline.evidence import configuration
from pipeline.inference import route
from pipeline.models import WorkItem
from pipeline.semantic_detection import documents, run, schedule
from pipeline.services import claim, reject
from policy_engine.service import evaluate
from records.models import Attachment, Blob, Category, Content, Incident, MailEvent, Policy, SemanticChunk
from records.references import save_reference
from records.semantic import MODEL, reindex
from records.semantic_status import semantic_status


@override_settings(MICE_COOKIE_SECURE=False)
class SemanticReviewTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user("review", role="admin", originals=True)
        self.blob = Blob.objects.create(sha="a" * 64, data=b"test", size=4)
        Category.objects.update_or_create(pk="SEMANTIC_REFERENCE", defaults={"name": "Semantic", "mode": "builtin", "active": True})
        Category.objects.update_or_create(pk="EMAIL", defaults={"name": "Email", "mode": "builtin", "active": True})
        Policy.objects.all().update(enabled=False)
        Policy.objects.create(name="Review", conditions={"categories": ["EMAIL", "SEMANTIC_REFERENCE"]})
        self.vector = [1.0] + [0.0] * 383

    def reference(self, template=False):
        prepared = {"data": b"reference", "name": "Review reference", "text": "reference text",
                    "fingerprint": {"document_template": {"kind": "passport"}} if template else {}}
        return save_reference(self.actor, prepared)

    def message(self, refs=()):
        text = "message body\nattachment text"
        content = Content.objects.create(normalized_sha=hashlib.sha256(text.encode()).hexdigest(), text=text,
            analysis={"findings": [{"category": "EMAIL", "risk": 20, "source": "regex"}],
                      "engine_errors": [], "skipped_checks": ["semantic"], "semantic_body_length": 12,
                      "configuration_snapshot": {"references": [{"id": r.pk} for r in refs]}})
        from records.models import Message
        message = Message.objects.create(original_sha_ref=self.blob, content=content, format="eml", status="ANALYZED")
        MailEvent.objects.create(message=message, source="test", source_key=message.pk)
        Attachment.objects.create(message=message, blob_sha_ref=self.blob, name="review.txt", mime="text/plain", status="ANALYZED", text="attachment text")
        return message

    def execute(self, job, handler):
        handler(claim(job.pk, "pr36-review"))
        job.refresh_from_db()
        self.assertEqual(job.status, "DONE")

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["mice_access_version"] = user.access_version
        session.save()

    @override_settings(MICE_SEMANTIC_AUTO_INDEX=True)
    def test_auto_index_and_template_exclusion(self):
        ref = self.reference()
        self.reference(template=True)
        jobs = WorkItem.objects.filter(kind="semantic.reindex")
        self.assertEqual(jobs.count(), 1)
        with patch("records.semantic.vectors", return_value=[self.vector]):
            self.execute(jobs.get(), reindex)
        self.assertEqual(SemanticChunk.objects.get().source_id, ref.pk)

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true", "MICE_ML_INFERENCE_ENABLED": "false", "MICE_LLM_INFERENCE_ENABLED": "false"})
    def test_body_attachment_findings_policy_and_worker_absence(self):
        ref = self.reference()
        SemanticChunk.objects.create(source_type="reference", source_id=ref.pk, chunk_index=0, text=ref.text, model=MODEL, embedding=self.vector)
        message = self.message([ref])
        semantic_job = route(message, "review")
        # Deterministic findings reach policies even if no semantic worker runs.
        self.execute(WorkItem.objects.get(kind="policy.evaluate"), evaluate)
        self.assertEqual(Incident.objects.get().findings[0]["category"], "EMAIL")
        with patch("records.semantic.vectors", side_effect=lambda parts: [self.vector for _ in parts]):
            self.execute(semantic_job, run)
        message.refresh_from_db()
        hits = [f for f in message.content.analysis["findings"] if f["category"] == "SEMANTIC_REFERENCE"]
        self.assertEqual({f["document_id"] for f in hits}, {"body", Attachment.objects.get().pk})
        self.assertEqual(documents(message.content, message.pk)[0][2], "message body")
        self.execute(WorkItem.objects.filter(kind="policy.evaluate", status="PENDING").get(), evaluate)
        self.assertEqual(len(Incident.objects.get().findings), 3)

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true"})
    def test_model_failure_preserves_other_findings_and_continues_policy(self):
        message = self.message([self.reference()])
        job = schedule(message, "failure")
        with patch("pipeline.semantic_detection.compare_documents", side_effect=RuntimeError("private text")):
            self.execute(job, run)
        message.refresh_from_db()
        self.assertEqual(message.status, "PARTIAL")
        self.assertEqual(message.content.analysis["findings"][0]["category"], "EMAIL")
        self.assertNotIn("private text", str(message.content.analysis))
        self.assertTrue(WorkItem.objects.filter(kind="policy.evaluate").exists())
        self.assertEqual(semantic_status({})["last_job"], "Ошибка или неполный результат")

    def test_terminal_failure_continues_policy(self):
        message = self.message([self.reference()])
        job = claim(schedule(message, "terminal").pk, "review")
        reject(job.pk, job.token, "failure")
        message.refresh_from_db()
        self.assertEqual(message.content.analysis["semantic_detection"]["status"], "PARTIAL")
        self.assertTrue(WorkItem.objects.filter(kind="policy.evaluate").exists())

    def test_no_references_skips_optional_queue(self):
        self.assertIsNone(schedule(self.message(), "empty"))

    def test_zero_vector_rejected(self):
        from records.semantic import vectors
        with patch("records.semantic.encoder") as encoder:
            encoder.return_value.embed.return_value = [[0.0] * 384]
            with self.assertRaises(ValueError):
                vectors(["text"])

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true"})
    def test_threshold_ui_changes_next_snapshot_without_restart(self):
        self.login(self.actor)
        for value in (.70, .95):
            response = self.client.post(reverse("detectors-page"), {"detector": "semantic", "enabled": "on", "threshold": value})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(configuration()["settings"]["semantic_detection"]["threshold"], value)
        message = self.message([self.reference()])
        message.content.analysis["configuration_snapshot"] = configuration()
        message.content.save(update_fields=["analysis"])
        self.assertEqual(schedule(message, "threshold").payload["threshold"], .95)
        response = self.client.get(reverse("detectors-page") + "?edit=semantic")
        self.assertContains(response, "0,95")

    def test_reference_access_matrix(self):
        for role, originals, expected_get, expected_post in [("admin", False, 403, 403), ("observer", True, 200, 403), ("analyst", True, 200, 400)]:
            user = User.objects.create_user(role, role=role, originals=originals)
            self.login(user)
            self.assertEqual(self.client.get(reverse("references-page")).status_code, expected_get)
            self.assertEqual(self.client.post(reverse("references-page"), {"action": "upload"}).status_code, expected_post)

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true"})
    def test_readiness_ignores_old_model_and_templates(self):
        ref = self.reference()
        self.reference(template=True)
        SemanticChunk.objects.create(source_type="reference", source_id=ref.pk, chunk_index=0, text=ref.text, model="old-model", embedding=self.vector)
        self.assertEqual(semantic_status({})["label"], "Требуется индексация")
        self.assertEqual(semantic_status({"semantic": False})["label"], "Отключён")

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true"})
    def test_missing_index_is_partial_without_loading_model(self):
        message = self.message([self.reference()])
        with patch("records.semantic.vectors") as vectors:
            self.execute(schedule(message, "missing"), run)
            vectors.assert_not_called()
        message.refresh_from_db()
        self.assertEqual(message.status, "PARTIAL")
        self.assertEqual(message.content.analysis["engine_errors"][0]["error"], "reference_index_unavailable")

    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "false"})
    def test_deployment_disabled_after_enqueue(self):
        message = self.message([self.reference()])
        with patch("pipeline.semantic_detection.compare_documents") as compare:
            self.execute(schedule(message, "disabled"), run)
            compare.assert_not_called()
        message.refresh_from_db()
        self.assertEqual(message.content.analysis["engine_errors"][0]["error"], "deployment_disabled")

    def test_superseded_job_does_not_load_model(self):
        message = self.message([self.reference()])
        job = schedule(message, "superseded")
        message.status = "PENDING"
        message.save(update_fields=["status"])
        with patch("pipeline.semantic_detection.compare_documents") as compare:
            self.execute(job, run)
            compare.assert_not_called()
        self.assertTrue(job.output["superseded"])