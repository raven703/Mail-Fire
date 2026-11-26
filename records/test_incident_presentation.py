"""Incident display identifiers and non-destructive grouping."""
from copy import deepcopy

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from identity.models import User
from policy_engine.templatetags.evidence_history import group_findings
from records.models import Blob, Incident, MailEvent, Message


class GroupedEvidenceTests(SimpleTestCase):
    def test_same_rule_groups_distinct_sources_without_mutation(self):
        first = {"category": "test", "historical_category": "Категория",
                 "rule_id": "rule-1", "source": "custom-keywords", "rule_version": "1",
                 "historical_rule": {"title": "Правило", "version": "1", "config": {"phrases": ["text"]}},
                 "document_id": "body", "excerpt": "body <script>sample</script>", "risk": 65}
        second = {**first, "document_id": "attachment-1", "excerpt": "attachment text", "risk": 80}
        rows = [first, second]
        before = deepcopy(rows)
        groups = group_findings(rows, {"attachment-1": "example.pdf"})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["risk"], 80)
        self.assertEqual([r["document_label"] for r in groups[0]["matches"]],
                         ["Тело письма", "Вложение: example.pdf"])
        self.assertEqual(rows, before)
        html = render_to_string("records/_evidence.html", {"findings": rows})
        self.assertEqual(html.count('class="evidence-card"'), 1)
        self.assertEqual(html.count("Сведения о детекторе"), 1)
        self.assertIn("Совпадений: 2", html)
        self.assertIn("attachment text", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_different_rules_revisions_and_categories_remain_distinct(self):
        first = {"category": "a", "rule_id": "1", "source": "custom-keywords", "risk": 75,
                 "historical_rule": {"version": "1", "config": {"phrases": ["old"]}}}
        rows = [first, {**first, "rule_id": "2"}, {**first, "category": "b"},
                {**first, "historical_rule": {"version": "2", "config": {"phrases": ["new"]}}}]
        self.assertEqual(len(group_findings(rows)), 4)


class IncidentNumberTests(TestCase):
    def make_incident(self, value):
        blob = Blob.objects.create(sha=f"{value:064x}", data=b"mail", size=4)
        message = Message.objects.create(original_sha_ref=blob, format="eml", status="ANALYZED")
        event = MailEvent.objects.create(message=message, source="test", source_key=str(value))
        return Incident.objects.create(message=message, event=event, risk=75, findings=[], policy_hits=[])

    def test_stable_numbers_and_search(self):
        first = self.make_incident(1)
        second = self.make_incident(2)
        first.refresh_from_db()
        second.refresh_from_db()
        number = first.number
        self.assertGreater(second.number, number)
        self.assertEqual(first.display_number, f"INC-{number:06d}")
        first.risk = 80
        first.status = "CONFIRMED"
        first.save(update_fields=["risk", "status"])
        first.refresh_from_db()
        self.assertEqual(first.number, number)
        user = User.objects.create_superuser("incident-number-admin", "test-password-long")
        self.client.force_login(user)
        session = self.client.session
        session["mice_access_version"] = user.access_version
        session.save()
        response = self.client.get("/incidents/", {"q": first.display_number, "status": "", "range": "24"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertContains(response, first.display_number)
        self.assertContains(response, f"/incidents/{first.pk}/")
        self.assertContains(self.client.get(f"/incidents/{first.pk}/"), first.display_number)
        second_number = second.number
        second.delete()
        third = self.make_incident(3)
        third.refresh_from_db()
        self.assertGreater(third.number, second_number)
