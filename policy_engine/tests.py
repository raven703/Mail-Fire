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
    def test_catalog_page_uses_shared_lifecycle_and_role_enforcement(self):
        from identity.models import User
        from records.models import Policy

        admin = User.objects.create_user("catalog-admin", "admin-test-password", role="admin")
        self.client.force_login(admin)
        session = self.client.session
        session["mice_access_version"] = admin.access_version
        session.save()
        self.assertContains(self.client.get("/policies/?new=1"), 'class="editor-dialog editor-dialog-wide"')
        response = self.client.post(
            "/policies/",
            {
                "name": "Catalog policy",
                "priority": "10",
                "min_risk": "40",
                "min_count": "1",
                "category_match": "any",
                "enabled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        policy = Policy.objects.get(name="Catalog policy")
        self.assertEqual(policy.version, 1)
        self.assertEqual(
            self.client.post("/policies/", {"id": policy.pk, "action": "archive"}).status_code, 302
        )
        policy.refresh_from_db()
        self.assertTrue(policy.archived)
        self.assertNotContains(self.client.get("/policies/"), "Catalog policy")
        self.assertContains(self.client.get("/policies/?archived=1"), "Catalog policy")
        observer = User.objects.create_user("catalog-observer", "observer-password", role="observer")
        self.client.force_login(observer)
        session = self.client.session
        session["mice_access_version"] = observer.access_version
        session.save()
        self.assertEqual(self.client.get("/policies/").status_code, 200)
        self.assertEqual(
            self.client.post("/policies/", {"id": policy.pk, "action": "delete"}).status_code, 403
        )

    def test_lifecycle_versions_and_category_validation_without_messages(self):
        from identity.models import User
        from policy_engine.catalog_service import PolicyError, mutate
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
