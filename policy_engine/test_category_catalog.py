"""Regression tests for the unified catalog; native evidence remains authoritative."""
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase

from app.category_catalog import possible_duplicates
from app.detection_evidence import analyze
from app.evidence import unique_findings
from identity.models import User
from policy_engine.category_pages import CategoryForm
from records.models import Category, CategoryRule
from records.category_picker import CategoryPicker


class BuiltinContextTests(SimpleTestCase):
    def run_analysis(self, documents, native=(), enabled=True, marker=True):
        rule = {"id": "ctx", "kind": "keywords", "title": "Context",
                "risk": 99, "config": {"phrases": ["sample token"], "match_type": "substring",
                                      "builtin_context": marker}}
        config = {"settings": {"normalizer": {"enabled": False}, "detectors": {"pii": enabled}},
                  "references": [], "groups": [{"category": {"id": "RU_SNILS", "name": "СНИЛС",
                  "mode": "builtin", "match_mode": "any"}, "rules": [rule]}]}
        with patch("app.detectors.detect", return_value=[]), patch(
            "app.advanced_detectors.pii", side_effect=lambda text, **kw: [
                dict(hit) for hit in native if hit.get("excerpt") in text
            ]
        ):
            return analyze({"text": "\n".join(d["text"] for d in documents), "documents": documents,
                            "attachments": [], "configuration": config})["findings"]

    def test_native_validation_is_authoritative(self):
        docs = [{"id": "body", "text": "sample token"}]
        base = {"category": "RU_SNILS", "source": "presidio", "rule_id": "ru_snils",
                "start": 0, "end": 12, "excerpt": "sample token", "risk": 40,
                "checksum_valid": False, "verification": "suspected"}
        self.assertEqual(self.run_analysis(docs), [])
        hits = self.run_analysis(docs, native=[base])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["risk"], 40)
        self.assertFalse(hits[0]["checksum_valid"])
        self.assertEqual(hits[0]["verification"], "suspected")
        self.assertEqual(len(hits[0]["context_matches"]), 1)
        self.assertEqual(self.run_analysis(docs, native=[base], enabled=False), [])
        self.assertNotIn("context_matches", self.run_analysis(docs, native=[base], marker=False)[0])

    def test_context_cannot_cross_documents(self):
        docs = [{"id": "body", "text": "native identifier"},
                {"id": "attachment", "text": "sample token"}]
        base = {"category": "RU_SNILS", "source": "presidio", "rule_id": "ru_snils",
                "start": 0, "end": 17, "excerpt": "native identifier", "risk": 60}
        hits = self.run_analysis(docs, native=[base])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["document_id"], "body")
        self.assertNotIn("context_matches", hits[0])

    def test_duplicate_hint_and_legacy_aliases(self):
        self.assertEqual(possible_duplicates("СНИЛС сотрудника", [("RU_SNILS", "СНИЛС")]),
                         [("RU_SNILS", "СНИЛС")])
        self.assertEqual(possible_duplicates("Финансовый план", [("RU_SNILS", "СНИЛС")]), [])
        source = {"category": "RU_INN", "source": "native", "risk": 60,
                  "start": 1, "end": 10, "document_id": "body"}
        hits = unique_findings([source, {**source, "category": "INN", "context_matches": [{"rule_id": "ctx"}]}])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["category"], "INN")
        self.assertEqual(hits[0]["context_matches"], [{"rule_id": "ctx"}])


class UnifiedCatalogTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("catalog-admin", "test-password-long")
        self.client.force_login(self.actor)
        session = self.client.session
        session["mice_access_version"] = self.actor.access_version
        session.save()

    def test_one_catalog_and_training_labels(self):
        response = self.client.get("/categories/")
        self.assertEqual(response.status_code, 200)
        ids = {row.pk for row in response.context["categories"]}
        self.assertIn("RU_SNILS", ids)
        self.assertNotIn("NORMAL", ids)
        self.assertNotIn("RU_INN", ids)
        self.assertNotIn("RU_PHONE", ids)
        self.assertContains(response, "Метод обнаружения")
        self.assertContains(self.client.get("/models/?tab=label"), "Метки датасетов")
        picker = CategoryPicker(policy=True)
        keys = {key for _, choices in picker.choices for key, _ in choices}
        self.assertNotIn("NORMAL", keys)
        self.assertNotIn("RU_INN", keys)
        old = CategoryPicker(policy=True, selected=["RU_INN"])
        self.assertIn("RU_INN", {key for _, choices in old.choices for key, _ in choices})

    def test_duplicate_warning_and_legacy_mode(self):
        data = {"name": "СНИЛС сотрудника", "group_name": "Персональные данные",
                "mode": "rules", "match_mode": "any", "active": "on"}
        form = CategoryForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("Возможный дубль", str(form.errors))
        form = CategoryForm({**data, "confirm_distinct": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["mode"], "custom")

    def test_context_rule_lifecycle_and_export(self):
        import json
        from policy_engine.rulepacks import export, parse
        before = Category.objects.values().get(pk="RU_SNILS")
        data = {"entity": "rule", "title": "Контекст", "kind": "keywords", "risk": "99",
                "priority": "100", "enabled": "on", "phrases": "sample token",
                "match_type": "substring"}
        response = self.client.post("/categories/RU_SNILS/?rule=new", data)
        self.assertEqual(response.status_code, 302)
        rule = CategoryRule.objects.get(category_id="RU_SNILS", config__builtin_context=True)
        self.assertEqual(rule.risk, 0)
        self.assertEqual(Category.objects.values().get(pk="RU_SNILS"), before)
        pack = parse(json.dumps(export()))
        context = next(c for c in pack["categories"] if c["id"] == "RU_SNILS")
        self.assertTrue(context["builtin_context"])
        self.assertTrue(context["rules"][0]["config"]["builtin_context"])
        self.assertEqual(self.client.post("/categories/RU_SNILS/", {"action": "archive"}).status_code, 403)
        self.assertEqual(self.client.post(f"/categories/RU_SNILS/rules/{rule.pk}/",
                         {"action": "delete_context"}).status_code, 302)
        self.assertFalse(CategoryRule.objects.filter(pk=rule.pk).exists())
        self.assertTrue(CategoryRule.all_objects.get(pk=rule.pk).deleted_at)
        self.assertEqual(Category.objects.values().get(pk="RU_SNILS"), before)
