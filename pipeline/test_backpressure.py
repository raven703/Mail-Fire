import base64
import threading
from datetime import timedelta
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from pipeline.models import WorkItem
from pipeline.parser_client import call
from pipeline.parser_errors import ParserRejected, ParserUnavailable
from pipeline.services import StaleAttempt, claim, defer, enqueue, finish, reject


class DeferralTests(TestCase):
    @override_settings(MICE_PARSER_MAX_WAIT_SECONDS=60)
    def test_prolonged_outage_stops_automatic_retries_and_is_visible(self):
        from pipeline.monitoring import parser_degradation
        job = enqueue('ingestion.parse', {}, 'long-outage')
        WorkItem.objects.filter(pk=job.pk).update(created_at=timezone.now()-timedelta(hours=2))
        running = claim(job.pk, 'worker')
        defer(job.pk, running.token, 'parser service=parser operation=mail status=503 reason=busy')
        job.refresh_from_db()
        self.assertEqual(job.status, 'CANCELLED')
        self.assertEqual(job.attempts, 0)
        self.assertIn('wait_budget_exceeded', job.error)
        state = parser_degradation()
        self.assertEqual(state['total'], 1)
        self.assertEqual(state['jobs'][0]['severity'], 'critical')
        self.assertEqual(state['jobs'][0]['deferrals'], 1)
        self.assertGreaterEqual(state['jobs'][0]['age_seconds'], 7200)
        self.assertIsNone(state['jobs'][0]['next_retry'])

    def test_many_busy_responses_do_not_exhaust_attempts_or_reuse_audit_number(self):
        job = enqueue('ingestion.parse', {'message_id': 'test'}, 'busy', max_attempts=1)
        for n in range(12):
            running = claim(job.pk, 'worker')
            defer(job.pk, running.token, 'parser service=parser operation=mail status=503 reason=busy', 5)
            job.refresh_from_db()
            self.assertEqual(job.attempts, 0)
            self.assertEqual(job.deferrals, n+1)
            self.assertEqual(job.status, 'PENDING')
            self.assertGreaterEqual((job.available_at-timezone.now()).total_seconds(), 4)
            self.assertIsNone(claim(job.pk, 'early'))
            with self.assertRaises(StaleAttempt):
                finish(job.pk, running.token, {})
            WorkItem.objects.filter(pk=job.pk).update(available_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(list(job.runs.order_by('number').values_list('number', flat=True)), list(range(1,13)))
        running = claim(job.pk, 'worker')
        finish(job.pk, running.token, {'ok': True})
        job.refresh_from_db()
        self.assertEqual(job.status, 'DONE')
        self.assertEqual(job.attempts, 1)

    def test_permanent_failure_goes_dead_once(self):
        job = enqueue('ingestion.parse', {}, 'invalid')
        running = claim(job.pk, 'worker')
        reject(job.pk, running.token, 'parser service=parser operation=mail status=422 reason=input_rejected')
        job.refresh_from_db()
        self.assertEqual(job.status, 'DEAD')
        self.assertEqual(job.attempts, 1)


@override_settings(MICE_PARSER_URL='http://secret:password@parser:8090')
class ClientClassificationTests(SimpleTestCase):
    def request(self, status, headers=None):
        transport = httpx.MockTransport(lambda request: httpx.Response(status, headers=headers,
            json={'secret': 'DO-NOT-LOG'}))
        factory = httpx.Client
        with patch('pipeline.parser_client.httpx.Client', side_effect=lambda **kw: factory(transport=transport, **kw)):
            return call('mail', b'private message', 'private filename')

    def test_http_classification_and_sanitization(self):
        for code in (408, 429, 500, 502, 503, 504):
            with self.assertRaises(ParserUnavailable) as caught:
                self.request(code, {'Retry-After': '99999', 'X-Parser-Reason': 'private-server-data'})
            self.assertEqual(caught.exception.retry_after, 300)
            self.assertEqual(caught.exception.status, code)
            self.assertNotIn('private', str(caught.exception))
            self.assertNotIn('password', str(caught.exception))
        for code in (301, 400, 401, 404, 413, 422):
            with self.assertRaises(ParserRejected):
                self.request(code)

    def test_transport_is_temporary_and_safe(self):
        with patch('pipeline.parser_client.httpx.Client', side_effect=httpx.ConnectError('password')):
            with self.assertRaises(ParserUnavailable) as caught:
                call('mail', b'body')
        self.assertNotIn('password', str(caught.exception))


class ServerBackpressureTests(SimpleTestCase):
    def test_bounded_queue_and_busy_response(self):
        from app import parser_service as module
        server = module.Server(('127.0.0.1', 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/parse'
        try:
            with patch.object(module, 'admission', threading.BoundedSemaphore(0)):
                response = httpx.post(url, json={'operation': 'mail', 'data': base64.b64encode(b'x').decode()}, trust_env=False)
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.headers['X-Parser-Reason'], 'queue_full')
                self.assertEqual(response.headers['Retry-After'], '5')
            # This is an HTTP admission test, not a parser dependency test.
            # Django-only CI intentionally does not install pydantic-settings.
            from types import SimpleNamespace
            import sys
            config = SimpleNamespace(settings=lambda: SimpleNamespace(parser_response_bytes=80 * 1024**2))
            with patch.object(module, 'local_call', return_value={'attachments': [], 'text': 'body'}), patch.dict(
                sys.modules, {'app.config': config}
            ):
                response = httpx.post(url, json={'operation': 'mail', 'data': base64.b64encode(b'x').decode()}, trust_env=False)
                self.assertEqual(response.status_code, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()