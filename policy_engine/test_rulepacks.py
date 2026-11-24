import json
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from policy_engine.rulepacks import page, parse


class RulepackTests(SimpleTestCase):
    def pack(self):
        return {"schema_version": 1, "name": "example", "categories": [{
            "id": "pack-example", "name": "Example", "group_name": "DLP",
            "rules": [{"kind": "keywords", "phrases": ["confidential"]}],
        }]}

    def test_original_flat_schema_normalizes_rule_config(self):
        result = parse(json.dumps(self.pack()))
        self.assertEqual(result["categories"][0]["rules"][0]["config"]["phrases"], ["confidential"])

    def test_rejects_system_id_unknown_fields_and_duplicates(self):
        pack = self.pack()
        pack["categories"][0]["id"] = "RU_INN"
        with self.assertRaises(ValueError):
            parse(json.dumps(pack))
        pack = self.pack()
        pack["categories"].append(pack["categories"][0])
        with self.assertRaises(ValueError):
            parse(json.dumps(pack))
        with self.assertRaises(ValueError):
            parse(json.dumps(self.pack() | {"secret": "unknown"}))

    def test_size_and_version(self):
        with self.assertRaises(ValueError):
            parse(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            parse(json.dumps(self.pack() | {"schema_version": True}))

    def test_non_admin_cannot_export(self):
        request = RequestFactory().get("/rulepacks/?export=1")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: False)
        self.assertEqual(page(request).status_code, 403)