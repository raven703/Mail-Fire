import hashlib
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from records.llm_configuration import LLMForm
from records.model_management import models, snapshot_hash


class ModelManagementTests(SimpleTestCase):
    def test_snapshot_matches_original_contract(self):
        rows = [{"text": "  Example   TEXT ", "labels": ["B", "A"]}]
        group = hashlib.sha256(b"example text").hexdigest()
        self.assertEqual(snapshot_hash(rows), hashlib.sha256((group + ":A,B").encode()).hexdigest())
        self.assertEqual(snapshot_hash(rows), snapshot_hash(list(reversed(rows))))

    def test_model_access_requires_admin(self):
        request = RequestFactory().get("/models/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: False)
        self.assertEqual(models(request).status_code, 403)

    def test_llm_endpoint_rejects_embedded_credentials(self):
        form = LLMForm()
        for value in ["http://provider.test", "https://user:password@provider.test", "https://provider.test/?key=secret"]:
            form.cleaned_data = {"base_url": value}
            from django.core.exceptions import ValidationError

            with self.assertRaises(ValidationError):
                form.clean_base_url()