from unittest.mock import patch

from django.test import SimpleTestCase

from app.detection_evidence import analyze
from app.fingerprints import fingerprint
from policy_engine.rule_config import validate_config


class EvidenceTests(SimpleTestCase):
    def payload(self, mode="any"):
        return {
            "text": "Confidential internal financial budget document for this quarter",
            "attachments": [],
            "configuration": {
                "settings": {}, "references": [],
                "groups": [{
                    "category": {"id": "custom", "mode": "custom", "match_mode": mode},
                    "rules": [
                        {"id": "keyword", "kind": "keywords", "title": "Keyword", "risk": 70,
                         "config": {"phrases": ["Confidential"]}},
                        {"id": "ml", "kind": "ml", "title": "ML", "risk": 70, "config": {}},
                    ],
                }],
            },
        }

    def test_any_matches_and_all_suppresses_unavailable_ml(self):
        with patch("app.advanced_detectors.pii", return_value=[]):
            any_result, all_result = analyze(self.payload()), analyze(self.payload("all"))
        self.assertTrue(any(hit["category"] == "custom" for hit in any_result["findings"]))
        self.assertFalse(any(hit["category"] == "custom" for hit in all_result["findings"]))
        self.assertEqual(all_result["engine_errors"], [{"engine": "category_ml", "error": "disabled"}])
        self.assertEqual(all_result["skipped_checks"], ["ml", "llm"])

    def test_reference_algorithm_and_normalizer_preserve_evidence(self):
        payload = self.payload()
        text = payload["text"]
        payload["configuration"]["settings"] = {"normalizer": {"enabled": True}}
        payload["configuration"]["references"] = [{"id": "reference", "text": text, "fingerprint": fingerprint(text)}]
        with patch("app.advanced_detectors.pii", return_value=[]):
            result = analyze(payload)
        hit = next(hit for hit in result["findings"] if hit["category"] == "REFERENCE_DOCUMENT")
        self.assertTrue(hit["similarity"]["exact"])
        self.assertTrue(result["normalization"]["enabled"])
        self.assertEqual(payload["text"], text)

    def test_native_rule_validation(self):
        self.assertEqual(validate_config("keywords", {"phrases": ["secret"]})["phrases"], ["secret"])
        for kind, config in [
            ("regex", {"pattern": "(a+)+"}), ("keywords", {"phrases": []}),
            ("keywords", {"phrases": ["secret"], "window": True}),
            ("reference", {"reference_ids": ["same", "same"]}),
            ("ml", {"min_confidence": 2}),
        ]:
            with self.subTest(kind=kind, config=config), self.assertRaises(ValueError):
                validate_config(kind, config)