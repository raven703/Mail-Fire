from types import SimpleNamespace

from django.test import SimpleTestCase

from pipeline.config import limits
from pipeline.handlers import handlers
from records.model_management import train_job


class TrainingRoutingTests(SimpleTestCase):
    def test_training_engines_use_disjoint_queues(self):
        self.assertEqual(handlers["training.model"][0], "training")
        self.assertEqual(handlers["training.neural"][0], "neural_training")
        self.assertEqual(limits("neural_training")["hard"], 7200)

    def test_incompatible_jobs_rejected_before_corpus_or_heavy_imports(self):
        for kind, engine in [("training.model", "rubert"), ("training.neural", "tfidf")]:
            with self.assertRaisesMessage(ValueError, "queue mismatch"):
                train_job(SimpleNamespace(kind=kind, payload={"engine": engine}))