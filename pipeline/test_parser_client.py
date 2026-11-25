from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from pipeline.parser_client import call


class ParserBoundaryTests(SimpleTestCase):
    @override_settings(MICE_PARSER_URL='http://parser:8090')
    def test_unified_http_envelope_is_not_base64_wrapped(self):
        import json
        import httpx
        request = {'original': 'ZW1s', 'configuration': {}, 'ocr_enabled': False}
        seen = []
        def respond(incoming):
            seen.append(incoming)
            return httpx.Response(200, json={'ok': True})
        factory = httpx.Client
        transport = httpx.MockTransport(respond)
        with patch('pipeline.parser_client.httpx.Client', side_effect=lambda **kw: factory(transport=transport, **kw)):
            self.assertEqual(call('analyze_message', json.dumps(request).encode()), {'ok': True})
        self.assertEqual(seen[0].url.path, '/analyze')
        self.assertEqual(json.loads(seen[0].content), request)

    @override_settings(MICE_PARSER_URL="")
    def test_no_local_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "local fallback forbidden"):
            call("mail", b"input")

    @override_settings(MICE_PARSER_URL="http://parser:8090", MICE_MAX_MESSAGE_BYTES=2)
    def test_input_limit_precedes_network(self):
        with patch("pipeline.parser_client.httpx.Client") as client:
            with self.assertRaisesRegex(ValueError, "input limit"):
                call("mail", b"oversized")
            client.assert_not_called()

    def test_operation_allowlist(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            call("execute", b"input")


class ExtractionContractTests(TestCase):
    def test_attachment_commit_and_redelivery_fencing_without_parsing_email(self):
        from pipeline.extraction import extract
        from pipeline.models import WorkItem
        from pipeline.services import StaleAttempt, claim, enqueue
        from records.models import Attachment, Blob, Message

        blob = Blob.objects.create(sha="a" * 64, data=b"contract", size=8)
        message = Message.objects.create(original_sha_ref=blob, format="eml")
        upstream = WorkItem.objects.create(
            kind="ingestion.parse",
            queue="ingestion",
            deduplication_key="contract-upstream",
            status="DONE",
            payload={"message_id": message.pk},
            output={
                "text": "body",
                "attachments": [{"name": "contract.txt", "mime": "text/plain", "blob_sha": blob.pk}],
            },
        )
        job = enqueue(
            "extraction.extract",
            {"message_id": message.pk, "parse_job_id": str(upstream.pk)},
            "contract-extract",
        )
        job = claim(job.pk, "contract-worker")
        with patch(
            "pipeline.extraction.call",
            return_value={"text": "attachment", "status": "PARTIAL", "details": {}},
        ):
            extract(job)
            with self.assertRaises(StaleAttempt):
                extract(job)
        self.assertEqual(Attachment.objects.filter(message=message).count(), 1)
        job.refresh_from_db()
        self.assertTrue(job.output["partial"])
        self.assertEqual(job.output["text"], "body\nattachment")
        message.refresh_from_db()
        self.assertEqual(message.status, "PENDING")
