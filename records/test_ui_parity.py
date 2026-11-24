from types import SimpleNamespace
from unittest.mock import Mock

from django.http import QueryDict
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase

from records.ui_filters import filter_dates, pagination_query


class NativeUIParityTests(SimpleTestCase):
    def test_changed_templates_compile(self):
        for name in ("records/message.html", "records/messages.html", "records/incidents.html",
                     "records/overview.html", "pipeline/operations.html", "records/_message_tabs.html",
                     "policy_engine/catalog.html", "records/reanalysis.html", "records/_risk_panels.html",
                     "records/_analytics.html", "pipeline/_resource_history.html", "records/attachment.html"):
            get_template(name)

    def test_evidence_cards_escape_saved_content(self):
        html = render_to_string("records/_evidence.html", {"findings": [{
            "category": "SECRET", "risk": 80, "excerpt": "<script>secret</script>",
            "rule_id": "rule-1", "version": "v1", "confidence": 0,
        }]})
        self.assertIn("evidence-card", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("rule-1", html)

    def test_viewer_has_original_tabs_and_passive_fallback(self):
        attachment = SimpleNamespace(pk="attachment", message_id="message", name="file.pdf", mime="application/pdf",
                                     status="ANALYZED", text="saved-text", blob_sha_ref=SimpleNamespace(size=12))
        html = render_to_string("records/attachment.html", {"attachment": attachment, "findings": []})
        for value in ("viewer-original", "viewer-text", "viewer-evidence", "data-document-viewer", "saved-text"):
            self.assertIn(value, html)
        html = render_to_string("records/attachment.html", {"attachment": attachment, "text_preview": True})
        self.assertNotIn("data-document-viewer", html)

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