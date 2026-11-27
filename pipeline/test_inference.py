from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pipeline.inference import enabled, route


class InferenceRoutingTests(SimpleTestCase):
    def test_original_any_all_category_semantics_with_ml(self):
        from app.categories import evaluate_groups

        category = SimpleNamespace(id="custom", mode="custom", match_mode="all")
        rules = [SimpleNamespace(id="keyword", kind="keywords", title="keyword", risk=50,
                                 config={"phrases": ["secret"]}),
                 SimpleNamespace(id="ml", kind="ml", title="classifier", risk=50, config={"min_confidence": .7})]
        groups = [{"category": category, "rules": rules}]
        scores = {"custom": {"matched": True, "confidence": .9}}
        self.assertEqual(len(evaluate_groups(groups, "secret", ml_scores=scores)), 2)
        self.assertEqual(evaluate_groups(groups, "public", ml_scores=scores), [])
        category.match_mode = "any"
        self.assertEqual(len(evaluate_groups(groups, "public", ml_scores=scores)), 1)
        category.match_mode = "all"
        self.assertEqual(evaluate_groups(groups, "secret", ml_scores=scores, available_engines={"keywords"}), [])

    def test_disabled_default_does_not_dispatch_optional_work(self):
        with patch.dict("os.environ", {}, clear=True), patch("policy_engine.service.request_evaluation") as evaluate:
            self.assertFalse(enabled("ml"))
            self.assertFalse(enabled("llm"))
            route(SimpleNamespace(pk="message", content_id="content"), "key")
            evaluate.assert_called_once_with("message", "key")

    def test_explicit_ml_gate_routes_id_only_durable_work(self):
        with patch.dict("os.environ", {"MICE_ML_INFERENCE_ENABLED": "true"}, clear=True), patch('policy_engine.service.request_evaluation') as evaluate, patch("pipeline.inference.enqueue") as enqueue, patch("pipeline.inference.MLModel.objects") as models, patch("pipeline.inference.Setting.objects") as settings, patch("records.models.Category.objects") as categories:
            models.filter.return_value.order_by.return_value = []
            settings.filter.return_value = []
            categories.filter.return_value.values.return_value = []
            route(SimpleNamespace(pk="message", content_id="content"), "key")
            evaluate.assert_called_once_with('message','before-inference:key')
            enqueue.assert_called_once_with("ml.infer", {"message_id": "message", "content_id": "content", "snapshot": {"models": [], "settings": {}, "categories": []}}, "inference:key")