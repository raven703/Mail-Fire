from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from pipeline.detection import detect


class DetectionCoordinatorTests(SimpleTestCase):
    @override_settings(MICE_CLAMAV_HOST="", MICE_OCR_ENABLED=True)
    def run_detection(self, scan_error=False):
        job = SimpleNamespace(pk="job", token="token", payload={"message_id": "message", "ocr_job_id": "ocr"})
        upstream = SimpleNamespace(kind="ocr.complete", payload={"message_id": "message", "extraction_job_id": "extraction"}, output={"text": "body", "attachment_ids": []})
        extraction = SimpleNamespace(payload={"parse_job_id": "parse"})
        parsed = SimpleNamespace(output={"text": "body"})
        message = SimpleNamespace(
            pk="message", original_sha_ref=SimpleNamespace(data=b"original"), sender="", recipients=[],
            save=lambda **kwargs: None,
        )

        def call(operation, data, name=""):
            if operation == "detection_evidence":
                return {"findings": [], "version": "rules-1", "engine_errors": [], "normalization": {}}
            if scan_error:
                raise RuntimeError("sandbox failed")
            return {"findings": [], "engines": {"gitleaks": "OK", "yara": "OK"}}

        with (
            patch("pipeline.detection.WorkItem.objects.get", side_effect=[upstream, extraction, parsed]),
            patch("pipeline.detection.Message.objects.select_related") as messages,
            patch("pipeline.detection.Message.objects.select_for_update") as locked,
            patch("pipeline.detection.Attachment.objects.filter") as attachments,
            patch("pipeline.detection.configuration", return_value={"settings": {"detectors": {"antivirus": False}}}),
            patch("pipeline.detection.call", side_effect=call),
            patch("pipeline.detection.transaction.atomic"),
            patch("pipeline.detection.locked_current"),
            patch("pipeline.detection.Content.objects.get_or_create", return_value=(SimpleNamespace(pk="content"), True)) as content,
            patch("pipeline.inference.route", return_value=SimpleNamespace(pk="policy")),
            patch("pipeline.detection.finish") as finish,
        ):
            messages.return_value.get.return_value = message
            locked.return_value.get.return_value = message
            attachments.return_value.select_related.return_value = []
            detect(job)
        return message, content.call_args.kwargs["defaults"]["analysis"], finish

    def test_complete_deterministic_analysis_with_disabled_optional_checks(self):
        message, analysis, finish = self.run_detection()
        self.assertEqual(message.status, "ANALYZED")
        self.assertEqual(analysis["skipped_checks"], ["antivirus", 'horizon', "llm", "ml", "semantic"])
        self.assertEqual(finish.call_args.args[2]["status"], "ANALYZED")

    def test_static_engine_failure_is_partial_not_clean(self):
        message, analysis, _ = self.run_detection(scan_error=True)
        self.assertEqual(message.status, "PARTIAL")
        self.assertEqual(analysis["engine_errors"], [{"engine": "static_scan", "error": "RuntimeError"}])