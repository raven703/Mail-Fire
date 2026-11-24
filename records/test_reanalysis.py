from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from records.reanalysis import bulk_reanalyze


class BulkReanalysisTests(SimpleTestCase):
    def test_observer_cannot_submit(self):
        request = RequestFactory().post("/messages/reanalyze/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda value: False)
        self.assertEqual(bulk_reanalyze(request).status_code, 403)

    def test_partial_results_and_idempotency_token_forwarded(self):
        request = RequestFactory().post("/messages/reanalyze/", {"message_ids": ["one", "two", "one"], "request_token": "a" * 32})
        request.user = SimpleNamespace(pk="actor", is_authenticated=True, has_perm=lambda value: True)
        with patch("records.reanalysis.request_reanalysis", side_effect=[SimpleNamespace(pk="job"), ValueError("busy")]) as dispatch:
            response = bulk_reanalyze(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dispatch.call_count, 2)
        self.assertContains(response, "busy")
        self.assertContains(response, "job")

    def test_empty_selection_rejected(self):
        request = RequestFactory().post("/messages/reanalyze/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda value: True)
        self.assertEqual(bulk_reanalyze(request).status_code, 400)