from pathlib import Path

from django.conf import settings
from django.http import HttpResponseRedirect
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase

from records.middleware import PrivateResponseMiddleware


class HTMXTests(SimpleTestCase):
    def test_login_redirect_reloads_shell(self):
        request = RequestFactory().get("/messages/", HTTP_HX_REQUEST="true")
        response = PrivateResponseMiddleware(lambda request: HttpResponseRedirect("/"))(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], "/")

    def test_normal_redirect_preserved(self):
        request = RequestFactory().get("/messages/")
        response = PrivateResponseMiddleware(lambda request: HttpResponseRedirect("/"))(request)
        self.assertEqual(response.status_code, 302)

    def test_shell_compiles_and_local_htmx_exists(self):
        get_template("identity/base.html")
        source = (Path(settings.BASE_DIR) / "static/vendor/htmx-2.0.11.min.js").read_text()
        self.assertIn("2.0.11", source)