"""Unified coordinator regression tests; parser boundary stays remote."""
import base64
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings

from pipeline.analysis import analyze
from pipeline.ingestion import accept
from pipeline.models import WorkItem
from pipeline.services import StaleAttempt, claim
from records.models import Attachment, Message


@override_settings(MICE_UNIFIED_ANALYSIS_ENABLED=True, MICE_OCR_ENABLED=False)
class UnifiedPipelineTests(TestCase):
    def make_job(self):
        record = accept(b"Subject: test\r\n\r\nbody", "upload", "unified-test", "test.eml")
        job = WorkItem.objects.get(payload__message_id=record.message_id)
        self.assertEqual((job.queue, job.kind), ("analysis", "analysis.analyze"))
        return record, claim(job.pk, "test")

    def response(self):
        identifier = str(uuid4())
        return {"parsed": {"subject": "test", "sender": "", "recipients": [], "headers": {}, "text": "body"},
                "attachments": [{"id": identifier, "name": "note.txt", "mime": "text/plain",
                                 "data": base64.b64encode(b"note").decode(), "text": "note",
                                 "status": "ANALYZED", "details": {}}],
                "text": "body\nnote", "timings": {"mail": .01},
                "evidence": {"findings": [], "version": "test", "engine_errors": [],
                             "skipped_checks": ["ml", "llm"], "normalization": {}}}

    def test_single_remote_call_atomic_completion_and_redelivery(self):
        record, job = self.make_job()
        config = {"settings": {"detectors": {"antivirus": False}}, "groups": [], "references": []}
        with patch("pipeline.analysis.configuration", return_value=config), patch(
            "pipeline.analysis.call", side_effect=lambda *a: self.response()
        ) as remote:
            analyze(job)
            self.assertEqual(remote.call_count, 1)
            self.assertEqual(remote.call_args.args[0], "analyze_message")
            with self.assertRaises(StaleAttempt):
                analyze(job)
        message = Message.objects.get(pk=record.message_id)
        self.assertEqual(message.status, "ANALYZED")
        self.assertEqual(message.content.text, "body\nnote")
        self.assertEqual(Attachment.objects.filter(message=message).count(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "DONE")
        self.assertEqual(WorkItem.objects.filter(kind="policy.evaluate").count(), 1)
        self.assertFalse(WorkItem.objects.filter(kind__in=["ingestion.parse", "extraction.extract",
                                                           "ocr.complete", "detection.detect"]).exists())

    def test_invalid_response_leaves_no_partial_commit(self):
        record, job = self.make_job()
        response = self.response()
        response["attachments"].append(dict(response["attachments"][0]))
        with patch("pipeline.analysis.configuration", return_value={}), patch(
            "pipeline.analysis.call", return_value=response
        ):
            with self.assertRaises(ValueError):
                analyze(job)
        self.assertFalse(Attachment.objects.filter(message_id=record.message_id).exists())
        self.assertIsNone(Message.objects.get(pk=record.message_id).content_id)
