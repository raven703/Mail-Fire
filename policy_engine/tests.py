"""Small algorithm/source checks only. No message fixtures or message processing."""

import ast
from pathlib import Path

from django.test import SimpleTestCase

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
