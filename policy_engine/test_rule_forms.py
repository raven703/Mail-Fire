from unittest.mock import patch

from django.test import SimpleTestCase

from policy_engine.rule_forms import StructuredRuleForm
from records.models import CategoryRule


class StructuredRuleTests(SimpleTestCase):
    def form(self, **values):
        with patch("policy_engine.rule_forms.Reference.objects") as refs:
            refs.order_by.return_value.values_list.return_value = [("ref", "Reference")]
            return StructuredRuleForm({"title": "Rule", "risk": 70, "priority": 100, "enabled": "on", **values})

    def test_all_engine_configs_without_json(self):
        cases = [({"kind": "keywords", "phrases": "secret phrase", "match_type": "word"}, "phrases"),
                 ({"kind": "regex", "pattern": "secret"}, "pattern"),
                 ({"kind": "reference", "reference_ids": ["ref"], "min_similarity": .8}, "reference_ids"),
                 ({"kind": "ml", "min_confidence": 0}, "min_confidence"),
                 ({"kind": "keywords", "match_type": "flexible", "term_0_text": "secret", "term_0_weight": 4,
                   "term_0_required": "on", "min_score": 3, "window": 12}, "terms")]
        for values, key in cases:
            form = self.form(**values)
            # Model uniqueness is unrelated to configuration validation.
            with patch.object(CategoryRule, "validate_unique"):
                self.assertTrue(form.is_valid(), form.errors)
            self.assertIn(key, form.save(commit=False).config)
            self.assertNotIn("config", form.fields)

    def test_original_validator_rejects_unsafe_regex(self):
        form = self.form(kind="regex", pattern="(secret)+")
        self.assertFalse(form.is_valid())