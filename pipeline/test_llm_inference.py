import json
from unittest.mock import patch

from django.test import SimpleTestCase

from app.llm_analyzer import DEFAULTS, analyze_configured
from app.text_normalizer import DEFAULTS as NORMALIZER_DEFAULTS


class LLMInferenceTests(SimpleTestCase):
    def test_selected_categories_and_response_filtering(self):
        options = DEFAULTS | {"enabled": True, "base_url": "https://provider.test/v1", "model": "local",
                              "routing": "selected", "categories": ["category"], "allow_external_content": True}
        with patch("app.llm_analyzer.httpx.Client") as client:
            response = client.return_value.__enter__.return_value.post.return_value
            response.json.return_value = {"choices": [{"message": {"content": json.dumps({"matches": [
                {"category": "category", "confidence": .9, "reason": "evidence"},
                {"category": "other", "confidence": .99},
                {"category": "category", "confidence": .1},
            ]})}}]}
            findings, errors = analyze_configured("email", [], options, NORMALIZER_DEFAULTS, {"category": "Name"})
            self.assertEqual(errors, [])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["source"], "llm")
            client.assert_called_once_with(timeout=30, follow_redirects=False, trust_env=False)

    def test_transfer_requires_explicit_authorization(self):
        options = DEFAULTS | {"enabled": True, "routing": "selected", "categories": ["category"]}
        with patch("app.llm_analyzer.httpx.Client") as client:
            findings, errors = analyze_configured("email", [], options, NORMALIZER_DEFAULTS, {"category": "Name"})
            self.assertEqual(findings, [])
            self.assertEqual(errors, ["llm_external_transfer_not_authorized"])
            client.assert_not_called()