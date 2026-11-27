"""Opt-in real MiniLM integration; never downloads model weights."""
import json
import os
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.test import override_settings

from pipeline.test_semantic_review import SemanticReviewTests
from pipeline.models import WorkItem
from pipeline.semantic_detection import run
from policy_engine.service import evaluate
from records.models import Attachment, Incident
from records.semantic import encoder, reindex, vectors


@skipUnless(os.environ.get("MICE_TEST_REAL_SEMANTIC") == "true", "Opt-in cached model test")
class OfflineSemanticTests(SemanticReviewTests):
    @override_settings(MICE_SEMANTIC_AUTO_INDEX=True)
    @patch.dict("os.environ", {"MICE_SEMANTIC_INFERENCE_ENABLED": "true", "HF_HUB_OFFLINE": "1"})
    def test_real_offline_index_findings_and_incident(self):
        corpus = json.loads((Path(__file__).resolve().parents[1] / "test-data/semantic-reference-small/corpus.json").read_text())
        text = corpus["references"][0]["text"]
        from records.references import save_reference
        ref = save_reference(self.actor, {"name": "offline.txt", "data": text.encode(), "text": text, "fingerprint": {}})
        encoder.cache_clear()
        # Fail any attempted external connection; pgvector uses psycopg/libpq.
        with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(len(vectors([text])[0]), 384)
            self.execute(WorkItem.objects.get(kind="semantic.reindex"), reindex)
            message = self.message([ref])
            content = message.content
            content.text = text + "\n" + text
            content.analysis["semantic_body_length"] = len(text)
            content.save(update_fields=["text", "analysis"])
            Attachment.objects.filter(message=message).update(text=text)
            from pipeline.inference import route
            job = route(message, "real-offline")
            self.execute(job, run)
            message.refresh_from_db()
            hits = [f for f in message.content.analysis["findings"] if f["category"] == "SEMANTIC_REFERENCE"]
            self.assertEqual(len(hits), 2)
            self.assertTrue(all(f["confidence"] > .99 for f in hits))
            # Run snapshots in order to exercise final incident enrichment.
            for job in WorkItem.objects.filter(kind="policy.evaluate").order_by("created_at", "pk"):
                self.execute(job, evaluate)
            self.assertEqual(len(Incident.objects.get().findings), 3)