"""Pure mail analysis and cached matcher regression tests."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from app.text_match import CompiledRuleSet, PreparedDocument, search


class PreparedMatcherTests(SimpleTestCase):
    def test_document_is_tokenized_once_for_both_modes(self):
        from app import text_match
        text = "Внутренние документы переданы сотрудникам."
        prepared = PreparedDocument(text)
        with patch.object(text_match, "tokenize", wraps=text_match.tokenize) as tokenize:
            self.assertTrue(prepared.positions(["документ"], True))
            self.assertTrue(prepared.positions(["документы"], False))
            self.assertTrue(prepared.positions(["внутренний", "документ"], True))
        self.assertEqual(tokenize.call_count, 1)

    def test_compiled_rules_preserve_hits_scores_spans_and_exclusions(self):
        text = "Передайте внутренний документ. В инструкции описан внутренний документ."
        config = {"match_type": "flexible", "terms": [
            {"text": "внутренний документ", "weight": 3, "required": True},
            {"text": "передать", "weight": 2, "required": False}],
            "window": 8, "min_score": 3, "exclude_phrases": ["В инструкции"]}
        rule = SimpleNamespace(id="rule", config=config)
        compiled = CompiledRuleSet().keywords(rule)
        kwargs = dict(mode="flexible", terms=config["terms"], window=8, min_score=3,
                      exclude_phrases=config["exclude_phrases"])
        self.assertEqual(search(text, **kwargs), search(text, prepared=PreparedDocument(text),
                                                        compiled=compiled, **kwargs))

