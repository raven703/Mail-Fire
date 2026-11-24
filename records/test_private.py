from types import SimpleNamespace

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from records.middleware import PrivateResponseMiddleware


class PrivateResponseTests(SimpleTestCase):
    def test_authenticated_response_is_not_cached(self):
        request = RequestFactory().get("/messages/")
        request.user = SimpleNamespace(is_authenticated=True)
        response = PrivateResponseMiddleware(lambda request: HttpResponse("private"))(request)
        self.assertEqual(response["Cache-Control"], "no-store, private")

    def test_public_response_cache_policy_not_changed(self):
        request = RequestFactory().get("/api/health")
        request.user = SimpleNamespace(is_authenticated=False)
        response = PrivateResponseMiddleware(lambda request: HttpResponse("ok"))(request)
        self.assertNotIn("Cache-Control", response)