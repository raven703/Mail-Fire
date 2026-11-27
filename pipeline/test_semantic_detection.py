from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from pipeline.semantic_detection import schedule, threshold, compare_documents


class SemanticRoutingTests(SimpleTestCase):
    def test_threshold_validation(self):
        for value in ("nan", "0", "1.1", "invalid"):
            with patch.dict("os.environ", {"MICE_SEMANTIC_THRESHOLD": value}):
                with self.assertRaises(ValueError):
                    threshold()

    def test_respects_detector_and_category_settings(self):
        for config in ({"settings": {"detectors": {"semantic": False}}},
                       {"inactive_categories": ["SEMANTIC_REFERENCE"]}):
            message = SimpleNamespace(pk="m", content_id="c",
                                      content=SimpleNamespace(analysis={"configuration_snapshot": config}))
            self.assertIsNone(schedule(message, "test"))

    def test_routes_before_policy_and_excludes_document_templates(self):
        from pipeline.inference import route
        config = {"references": [{"id": "ref", "fingerprint": {}},
                                 {"id": "template", "fingerprint": {"document_template": { "kind": "passport" }}}]}
        message = SimpleNamespace(pk="m", content_id="c",
                                  content=SimpleNamespace(analysis={"configuration_snapshot": config}))
        with patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true", "MICE_SEMANTIC_THRESHOLD": ".85"}, clear=True), patch("pipeline.semantic_detection.enqueue") as enqueue:
            route(message, "test")
            enqueue.assert_called_once_with("semantic.detect", {"message_id": "m", "content_id": "c",
                                             "reference_ids": ["ref"], "threshold": .85}, "semantic-detect:test")

    def test_no_references_does_not_load_model(self):
        with patch("records.semantic.vectors") as vectors:
            self.assertEqual(compare_documents([("body", "", "text")], [], .85), ([], [], "NO_REFERENCES"))
            vectors.assert_not_called()


class SemanticMatchingTests(TestCase):
    def test_indexed_reference_match_and_missing_index(self):
        from records.models import Blob, Reference, SemanticChunk
        from records.semantic import MODEL
        blob = Blob.objects.create(sha="a" * 64, data=b"x", size=1)
        ref = Reference.objects.create(name="Plan", text="reference text", fingerprint={}, blob_sha_ref=blob)
        missing = Reference.objects.create(name="Missing", text="other", fingerprint={}, blob_sha_ref=blob)
        vector = [1.0] + [0.0] * 383
        SemanticChunk.objects.create(source_type="reference", source_id=ref.pk, chunk_index=0,
                                     text="reference text", model=MODEL, embedding=vector)
        with patch("records.semantic.vectors", return_value=[vector]):
            hits, errors, state = compare_documents([("body", "", "query text")], [ref.pk, missing.pk], .85)
        self.assertEqual(state, "PARTIAL")
        self.assertEqual(errors[0]["error"], "reference_index_unavailable")
        self.assertEqual(hits[0]["category"], "SEMANTIC_REFERENCE")
        self.assertEqual(hits[0]["reference_id"], ref.pk)
        self.assertAlmostEqual(hits[0]["confidence"], 1.0)
        with patch("records.semantic.vectors", return_value=[[0.0, 1.0] + [0.0] * 382]):
            self.assertEqual(compare_documents([("body", "", "unrelated")], [ref.pk], .85), ([], [], "OK"))
