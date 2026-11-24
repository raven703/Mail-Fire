from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from records.garbage_collection import contains
from records.semantic import chunks, page, vectors


class SemanticGCTests(SimpleTestCase):
    def test_original_chunk_boundaries_and_overlap(self):
        words = [str(index) for index in range(400)]
        parts = chunks(" ".join(words))
        self.assertEqual(parts[0].split(), words[:180])
        self.assertEqual(parts[1].split(), words[140:320])

    def test_nested_durable_references(self):
        self.assertTrue(contains({"attachments": [{"blob_sha": "digest"}]}, "digest"))
        self.assertFalse(contains({"text": "digest is part of text"}, "digest"))
        self.assertTrue(contains(["content", "identifier"], "identifier"))

    def test_invalid_embedding_fails_closed(self):
        with patch("records.semantic.encoder") as encoder:
            encoder.return_value.embed.return_value = [[0.0] * 383]
            with self.assertRaises(ValueError):
                vectors(["query"])

    def test_originals_required(self):
        request = RequestFactory().get("/semantic/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: False)
        self.assertEqual(page(request).status_code, 403)