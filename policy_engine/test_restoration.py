import copy
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase

from app.categories import evaluate_groups
from app.text_match import search
from identity.models import User
from policy_engine.restoration import compare, load_configuration, restore
from records.models import Category, CategoryRule, Policy, Setting


class RestorationTests(TestCase):
    def setUp(self):
        self.expected = load_configuration()

    def test_exact_idempotent_restore_and_no_unrelated_data(self):
        Setting.objects.create(key="ui:keep", value={"theme": "dark"})
        unrelated = Policy.objects.create(name="Keep existing", conditions={})
        restore(self.expected)
        before = list(CategoryRule.objects.order_by("pk").values())
        call_command("restore_original_dlp", stdout=StringIO())
        call_command("restore_original_dlp", check=True, stdout=StringIO())
        self.assertEqual(before, list(CategoryRule.objects.order_by("pk").values()))
        report = compare(self.expected)
        self.assertEqual(report["differences"], [])
        self.assertEqual((report["system_categories"], report["custom_categories"], report["weighted_terms"]), (19, 12, 128))
        self.assertEqual(Category.objects.count(), 31)
        self.assertEqual(CategoryRule.objects.count(), 33)
        self.assertEqual(Policy.objects.count(), 9)
        self.assertIn(unrelated.pk, report["extras"]["policies"])
        self.assertEqual(Setting.objects.get(pk="ui:keep").value, {"theme": "dark"})
        self.assertFalse(User.objects.exists())

    def test_original_weighted_rules_morphology_and_threshold(self):
        for spec in self.expected["rules"]:
            config = spec["config"]
            if config.get("match_type") != "flexible":
                continue
            text = " ".join(term["text"] for term in config["terms"])
            self.assertTrue(search(text, mode="flexible", **{k: v for k, v in config.items() if k != "match_type"}), spec["title"])
        config = self.expected["rules"][0]["config"]
        self.assertTrue(search("Внутренние прогнозы выручки на квартал", mode="flexible", **{k: v for k, v in config.items() if k != "match_type"}))
        self.assertFalse(search("прогноз", mode="flexible", **{k: v for k, v in config.items() if k != "match_type"}))
        self.assertFalse(search("прогноз " + "слово " * 30 + "выручка", mode="flexible", **{k: v for k, v in config.items() if k != "match_type"}))

    def test_any_all_and_exclusions_without_algorithm_changes(self):
        spec = self.expected["rules"][0]
        rule = SimpleNamespace(**spec)
        missing = SimpleNamespace(**{**spec, "id": "missing", "config": {"phrases": ["несуществующая фраза"]}})
        category = SimpleNamespace(id=spec["category_id"], mode="custom", match_mode="any")
        group = {"category": category, "rules": [rule, missing]}
        self.assertTrue(evaluate_groups([group], "прогноз выручки"))
        category.match_mode = "all"
        self.assertFalse(evaluate_groups([group], "прогноз выручки"))
        config = {**spec["config"], "exclude_phrases": ["учебный пример"]}
        self.assertFalse(search("прогноз выручки учебный пример", mode="flexible", **{k: v for k, v in config.items() if k != "match_type"}))

    def test_weight_editor_get_and_post_preserves_original_parameters(self):
        restore(self.expected)
        admin = User.objects.create_superuser("restore-admin", "test-password-long")
        self.client.force_login(admin)
        session = self.client.session
        session["mice_access_version"] = admin.access_version
        session.save()
        rule = CategoryRule.objects.get(pk=self.expected["rules"][0]["id"])
        original = copy.deepcopy(rule.config)
        url = f"/categories/{rule.category_id}/rules/{rule.pk}/"
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'name="term_0_weight"')
        form = response.context["form"]
        data = {key: form[key].value() for key in form.fields if form[key].value() is not None}
        data["entity"] = "rule"
        data["term_0_weight"] = 9
        for key in list(data):
            if data[key] is False:
                del data[key]
        response = self.client.post(url, data, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 302)
        rule.refresh_from_db()
        self.assertEqual(rule.config["terms"][0]["weight"], 9)
        self.assertEqual(set(rule.config), set(original))
        for key, value in original.items():
            if key != "terms":
                self.assertEqual(rule.config[key], value)
        restore(self.expected)
        self.assertEqual(CategoryRule.objects.get(pk=rule.pk).config, original)