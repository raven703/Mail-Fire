from types import SimpleNamespace
from unittest.mock import Mock

from django.http import QueryDict
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase

from records.ui_filters import filter_dates, pagination_query


class NativeUIParityTests(SimpleTestCase):
    def test_changed_templates_compile(self):
        for name in ("records/message.html", "records/messages.html", "records/incidents.html",
                     "records/overview.html", "pipeline/operations.html", "records/_message_tabs.html"):
            get_template(name)

    def test_pagination_preserves_all_filter_values(self):
        query = pagination_query(QueryDict("category=A&category=B&start=2026-11-01T12%3A00&page=2"))
        self.assertIn("category=A&category=B", query)
        self.assertNotIn("page=", query)

    def test_bad_date_is_ignored_and_valid_date_applied(self):
        rows = Mock()
        self.assertIs(filter_dates(rows, {"start": "not-a-date"}), rows)
        rows.filter.assert_not_called()
        filter_dates(rows, {"start": "2026-11-01T12:00"})
        self.assertIsNotNone(rows.filter.call_args.kwargs["created_at__gte"].tzinfo)

    def test_message_tabs_do_not_expose_content_without_permission(self):
        message = SimpleNamespace(pk="message", content=SimpleNamespace(text="secret-text", analysis={}), headers={})
        html = render_to_string("records/message.html", {"message": message, "perms": {"identity": {"view_originals": False}}})
        self.assertNotIn("secret-text", html)