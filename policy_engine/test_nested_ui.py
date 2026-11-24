from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase

from policy_engine.pages import catalog


class NestedCategoryUITests(SimpleTestCase):
    def test_nested_templates_compile(self):
        get_template("policy_engine/catalog.html")
        get_template("policy_engine/_nested_category.html")
        get_template("records/_incident_training.html")

    def test_observer_cannot_edit_nested_category(self):
        request = RequestFactory().post("/policies/", {"action": "edit_category:category"})
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda value: value == "identity.access_mice")
        with patch("policy_engine.pages.CategoryForm") as form:
            response = catalog(request)
        self.assertEqual(response.status_code, 403)
        form.assert_not_called()