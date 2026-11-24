"""Small algorithm/source checks only. No message fixtures or message processing."""

import ast
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from policy_engine.rules import policy_matches


class PolicyRulesTests(SimpleTestCase):
    def test_any_all_and_thresholds(self):
        findings = [{"category": "A", "risk": 60}, {"category": "B", "risk": 40}]
        options = {"categories": ["A", "B"], "min_risk": 50, "category_match": "any"}
        self.assertEqual(policy_matches(findings, options), findings[:1])
        self.assertEqual(policy_matches(findings, {**options, "category_match": "all"}), [])

    def test_extracted_algorithms_are_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        extracted = ast.parse((root / "policy_engine/rules.py").read_text())
        functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in extracted.body
            if isinstance(node, ast.FunctionDef)
        }
        for file, name in [("app/processing.py", "policy_matches"), ("app/mail.py", "classify_direction")]:
            source = ast.parse((root / file).read_text())
            original = next(
                node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == name
            )
            self.assertEqual(functions[name], ast.dump(original, include_attributes=False))


class PolicyCatalogTests(TestCase):
    def test_lifecycle_versions_and_category_validation_without_messages(self):
        from identity.models import User
        from policy_engine.catalog_views import PolicyError, mutate
        from policy_engine.models import PolicyRevision
        from records.models import Category, Policy

        actor = User.objects.create_user("policy-admin", "policy-password", role="admin")
        Category.objects.create(id="A", name="Category A", mode="builtin")
        body = {"name": "Test policy", "categories": ["A"], "category_match": "all"}
        created = mutate(actor, body)
        self.assertEqual(created["version"], 1)
        updated = mutate(actor, {**body, "name": "Updated policy"}, created["id"])
        self.assertEqual(updated["version"], 2)
        mutate(actor, {}, created["id"], "archive")
        self.assertTrue(Policy.objects.get(pk=created["id"]).archived)
        mutate(actor, {}, created["id"], "restore")
        self.assertFalse(Policy.objects.get(pk=created["id"]).enabled)
        with self.assertRaises(PolicyError):
            mutate(actor, {"name": "Invalid", "category_match": "all"})
        mutate(actor, {}, created["id"], "delete")
        self.assertFalse(Policy.objects.exists())
        self.assertTrue(PolicyRevision.objects.filter(policy_id=created["id"]).exists())
