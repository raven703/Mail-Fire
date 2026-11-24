from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from records.workspace import access, original_message, update_investigation


class WorkspaceTests(SimpleTestCase):
    def test_originals_capability_is_independent(self):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda value: value != "identity.view_originals")
        self.assertIsNone(access(request))
        self.assertEqual(original_message(request, "message").status_code, 403)

    def test_observer_cannot_mutate(self):
        request = RequestFactory().post("/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda value: value == "identity.access_mice")
        self.assertEqual(access(request, write=True).status_code, 403)

    def test_investigation_updates_are_atomic_and_audited(self):
        actor = SimpleNamespace(pk="actor", has_perm=lambda value: True)
        row = SimpleNamespace(pk="incident", status="NEW", assignee_ref_id=None, save=lambda **kwargs: None)
        with (
            patch("django.db.transaction.Atomic.__enter__"),
            patch("django.db.transaction.Atomic.__exit__"),
            patch("records.workspace.User.objects.select_for_update") as users,
            patch("records.workspace.Incident.objects.select_for_update") as locked,
            patch("records.workspace.Comment.objects.create") as comment,
            patch("records.workspace.Audit.objects.create") as audit,
        ):
            users.return_value.get.return_value = actor
            locked.return_value.get.return_value = row
            update_investigation(actor, "incident", status="REVIEW", comment=" review ")
        self.assertEqual(row.status, "REVIEW")
        comment.assert_called_once_with(incident=row, account_id="actor", text="review")
        self.assertEqual(audit.call_args.kwargs["details"]["before"]["status"], "NEW")

    def test_incident_template_hides_sensitive_findings(self):
        incident = SimpleNamespace(
            pk="incident", message_id="message", status="NEW", risk=70,
            policy_hits=[{"name": "Policy", "findings": [{"excerpt": "sensitive-evidence"}]}],
        )
        context = {"incident": incident, "perms": {"identity": {"view_originals": False}}}
        self.assertNotIn("sensitive-evidence", render_to_string("records/incident.html", context))
        context["perms"]["identity"]["view_originals"] = True
        self.assertIn("sensitive-evidence", render_to_string("records/incident.html", context))