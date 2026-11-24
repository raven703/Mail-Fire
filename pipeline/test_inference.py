from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pipeline.inference import enabled, route


class InferenceRoutingTests(SimpleTestCase):
    def test_disabled_default_does_not_dispatch_optional_work(self):
        with patch.dict("os.environ", {}, clear=True), patch("policy_engine.service.request_evaluation") as evaluate:
            self.assertFalse(enabled("ml"))
            self.assertFalse(enabled("llm"))
            route(SimpleNamespace(pk="message", content_id="content"), "key")
            evaluate.assert_called_once_with("message", "key")

    def test_explicit_ml_gate_routes_id_only_durable_work(self):
        with patch.dict("os.environ", {"MICE_ML_INFERENCE_ENABLED": "true"}, clear=True), patch("pipeline.inference.enqueue") as enqueue:
            route(SimpleNamespace(pk="message", content_id="content"), "key")
            enqueue.assert_called_once_with("ml.infer", {"message_id": "message", "content_id": "content"}, "inference:key")