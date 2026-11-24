from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from records.retention import DEFAULTS, RetentionForm, cleanup, expired, legal_hold


class RetentionTests(SimpleTestCase):
    def test_incident_specific_retention(self):
        now = datetime(2026, 11, 24)
        created = now - timedelta(days=40)
        self.assertTrue(expired(created, [], DEFAULTS, now))
        self.assertFalse(expired(created, ["NEW"], DEFAULTS, now))
        self.assertFalse(expired(created, ["CONFIRMED"], DEFAULTS, now))
        values = DEFAULTS | {"confirmed_days": 10}
        self.assertTrue(expired(created, ["NEW", "CONFIRMED"], values, now))

    def test_configuration_bounds(self):
        self.assertTrue(RetentionForm(DEFAULTS).is_valid())
        self.assertFalse(RetentionForm(DEFAULTS | {"ordinary_days": 0}).is_valid())

    def test_paused_cleanup_does_not_read_messages(self):
        job = SimpleNamespace(pk="job", token="token")
        with (
            patch("records.retention.config", return_value=DEFAULTS),
            patch("records.retention.Message.objects.filter") as messages,
            patch("records.retention.transaction.atomic"),
            patch("records.retention.locked_current", return_value=SimpleNamespace(output={})),
            patch("records.retention.finish") as finish,
        ):
            cleanup(job)
        messages.assert_not_called()
        self.assertTrue(finish.call_args.args[2]["paused"])

    def test_hold_requires_admin_and_reason(self):
        request = RequestFactory().post("/hold/", {"enabled": "true", "reason": "a"})
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: True)
        self.assertEqual(legal_hold(request, "message").status_code, 400)
        request.user.has_perm = lambda permission: False
        self.assertEqual(legal_hold(request, "message").status_code, 403)