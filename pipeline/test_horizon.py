"""Horizon integration on Django's isolated test database. No GPU/model needed."""

import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from identity.models import User
from pipeline.evidence import configuration
from pipeline.horizon_detection import run, schedule
from pipeline.inference import route
from pipeline.models import WorkItem
from pipeline.services import claim, reject
from policy_engine.service import evaluate
from records.models import (
    Blob,
    Category,
    CategoryRule,
    Content,
    Incident,
    MailEvent,
    Message,
    Policy,
    Setting,
)


@override_settings(MICE_COOKIE_SECURE=False)
class HorizonIntegrationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user("horizon-admin", role="admin")
        self.category = Category.objects.create(
            pk="pack-ru2-financial-plans", name="Financial", mode="custom", match_mode="any"
        )
        self.rule = CategoryRule.objects.create(
            category=self.category,
            kind="horizon",
            risk=50,
            title="Horizon",
            config={
                "positive_hypotheses": ["Internal financial plans"],
                "excluding_hypotheses": [],
                "threshold": 0.5,
                "combine": "single",
                "aggregation": "max",
            },
        )
        self.keyword = CategoryRule.objects.create(
            category=self.category, kind="keywords", risk=50, title="Keywords", config={"phrases": ["secret"]}
        )
        self.blob = Blob.objects.create(sha="c" * 64, data=b"test", size=4)
        Policy.objects.all().update(enabled=False)
        Policy.objects.create(
            name="Test", conditions={"categories": [self.category.pk], "min_risk": 40, "min_count": 1}
        )
        Setting.objects.update_or_create(pk="detectors", defaults={"value": {"horizon": True}})

    def message(self):
        conf = configuration()
        conf["settings"]["detectors"] = {"horizon": True}
        hit = {
            "category": self.category.pk,
            "source": "custom-keywords",
            "rule_id": self.keyword.pk,
            "risk": 50,
            "start": 0,
            "end": 6,
            "document_id": "body",
        }
        content = Content.objects.create(
            normalized_sha="d" * 64,
            text="secret budget",
            analysis={
                "findings": [hit],
                "configuration_snapshot": conf,
                "semantic_body_length": 13,
                "skipped_checks": ["horizon"],
            },
        )
        message = Message.objects.create(
            original_sha_ref=self.blob, content=content, format="eml", status="ANALYZED"
        )
        MailEvent.objects.create(message=message, source="test", source_key=message.pk)
        return message

    def execute(self, job, handler):
        handler(claim(job.pk, "horizon-test"))
        job.refresh_from_db()
        self.assertEqual(job.status, "DONE")

    @patch.dict(
        "os.environ",
        {
            "MICE_HORIZON_INFERENCE_ENABLED": "true",
            "MICE_SEMANTIC_INFERENCE_ENABLED": "false",
            "MICE_ML_INFERENCE_ENABLED": "false",
            "MICE_LLM_INFERENCE_ENABLED": "false",
        },
    )
    def test_success_existing_policy_idempotence_and_metadata(self):
        message = self.message()
        job = route(message, "test")
        self.assertEqual(job.kind, "horizon.infer")
        self.assertTrue(WorkItem.objects.filter(kind="policy.evaluate").exists())
        with patch("app.horizon.score_pairs", return_value=([0.9], "weights")):
            # Default scorer binding deliberately replaced at the entry point.
            from app.horizon import analyze_document

            with patch(
                "app.horizon.analyze_document",
                side_effect=lambda t, r, **kw: analyze_document(
                    t, r, scorer=lambda p: ([0.9] * len(p), "weights"), **kw
                ),
            ):
                self.execute(job, run)
        message.refresh_from_db()
        findings = message.content.analysis["findings"]
        hit = next(f for f in findings if f["source"] == "custom-horizon")
        self.assertEqual(hit["horizon_threshold"], 0.5)
        self.assertEqual(hit["model_weights_sha256"], "weights")
        self.assertIsNone(schedule(message, "no-repeat"))
        for policy_job in WorkItem.objects.filter(kind="policy.evaluate").order_by("created_at"):
            self.execute(policy_job, evaluate)
        self.assertEqual(Incident.objects.filter(message=message).count(), 1)
        incident = Incident.objects.get(message=message)
        self.assertEqual(incident.risk, 50)
        self.assertIn("custom-horizon", {f["source"] for f in incident.findings})

    @patch.dict("os.environ", {"MICE_HORIZON_INFERENCE_ENABLED": "true"})
    def test_missing_model_preserves_existing_detection(self):
        message = self.message()
        job = schedule(message, "missing")
        with patch("app.horizon.model_directory", side_effect=FileNotFoundError):
            self.execute(job, run)
        message.refresh_from_db()
        self.assertEqual(message.status, "PARTIAL")
        self.assertIn("horizon", message.content.analysis["skipped_checks"])
        self.assertTrue(any(f["source"] == "custom-keywords" for f in message.content.analysis["findings"]))

    def test_terminal_worker_failure(self):
        message = self.message()
        job = claim(schedule(message, "terminal").pk, "worker")
        reject(job.pk, job.token, "forced terminal failure")
        message.refresh_from_db()
        self.assertEqual(message.status, "PARTIAL")
        self.assertEqual(message.content.analysis["engine_errors"][-1]["error"], "worker_terminal_failure")

    def test_seed_only_existing_categories_disabled_and_no_overwrite(self):
        defaults = json.loads((Path(__file__).resolve().parents[1] / "app/horizon_defaults.json").read_text())
        for cid in set(defaults) - {self.category.pk}:
            Category.objects.create(pk=cid, name=cid, mode="custom")
        before = Category.objects.count()
        call_command("install_horizon_defaults")
        self.assertEqual(Category.objects.count(), before)
        self.assertEqual(CategoryRule.objects.filter(kind="horizon", enabled=False).count(), 12)
        call_command("install_horizon_defaults")
        self.assertEqual(CategoryRule.objects.filter(kind="horizon").count(), 13)

    def test_category_ui_saves_hypotheses_and_new_snapshot(self):
        self.client.force_login(self.actor)
        session = self.client.session
        session["mice_access_version"] = self.actor.access_version
        session.save()
        response = self.client.get(f"/categories/{self.category.pk}/?edit=1")
        self.assertContains(response, "Horizon Zero-shot")
        self.assertContains(response, "positive_hypotheses")
        response = self.client.get("/detectors/?edit=horizon")
        self.assertContains(response, "Horizon")

    def test_sibling_ml_completion_reuses_horizon_without_losing_any_all(self):
        from pipeline.inference import run as infer
        from records.models import InferenceArtifact

        message = self.message()
        source_id = message.content_id
        self.category.match_mode = "all"
        self.category.save()
        CategoryRule.objects.create(
            category=self.category, kind="ml", title="ML", risk=50, config={"min_confidence": 0.7}
        )
        message.content.analysis["configuration_snapshot"] = configuration()
        message.content.save()
        prediction = {
            "matched": True,
            "confidence": 0.9,
            "excerpt": "secret budget",
            "start": 0,
            "end": 13,
            "horizon_score": 0.9,
            "horizon_threshold": 0.5,
        }
        newer = Content.objects.create(
            normalized_sha="e" * 64,
            text=message.content.text,
            analysis={
                **message.content.analysis,
                "horizon_detection": {
                    "status": "OK",
                    "checks": [{"document_id": "body", "predictions": {self.rule.pk: prediction}}],
                },
            },
        )
        message.content = newer
        message.save()
        sha = __import__("hashlib").sha256(b"artifact").hexdigest()
        InferenceArtifact.objects.create(pk=sha, data=b"artifact")
        from pipeline.services import enqueue

        snapshot = {
            "models": [{"id": "model", "engine": "tfidf", "category_id": None, "metrics": {}, "sha256": sha}],
            "categories": [{"id": self.category.pk, "mode": "custom"}],
            "settings": {},
        }
        job = enqueue(
            "ml.infer", {"message_id": message.pk, "content_id": source_id, "snapshot": snapshot}, "sibling"
        )
        with (
            patch.dict("os.environ", {"MICE_ML_INFERENCE_ENABLED": "true"}),
            patch(
                "app.ml_runtime.infer_models",
                return_value=(
                    [
                        {
                            "category": self.category.pk,
                            "matched": True,
                            "confidence": 0.95,
                            "engine": "tfidf",
                            "model_id": "model",
                        }
                    ],
                    [],
                ),
            ),
        ):
            self.execute(job, infer)
        message.refresh_from_db()
        self.assertEqual(
            {f["source"] for f in message.content.analysis["findings"]},
            {"custom-keywords", "custom-horizon", "custom-ml"},
        )

    def test_superseded_horizon_does_not_load_model(self):
        message = self.message()
        job = schedule(message, "stale")
        message.status = "PENDING"
        message.save()
        with patch("pipeline.horizon_detection.evaluate_documents") as evaluator:
            self.execute(job, run)
            evaluator.assert_not_called()

    @patch.dict("os.environ", {"MICE_HORIZON_INFERENCE_ENABLED": "true"})
    def test_horizon_queued_before_sibling_content_advance_still_runs(self):
        message = self.message()
        job = schedule(message, "sibling-first")
        newer = Content.objects.create(
            normalized_sha="f" * 64, text=message.content.text, analysis=dict(message.content.analysis)
        )
        message.content = newer
        message.save()
        from app.horizon import analyze_document

        with patch(
            "app.horizon.analyze_document",
            side_effect=lambda t, r, **kw: analyze_document(
                t, r, scorer=lambda p: ([0.9] * len(p), "weights"), **kw
            ),
        ):
            self.execute(job, run)
        message.refresh_from_db()
        self.assertEqual(message.content.analysis["horizon_detection"]["status"], "OK")
        self.assertTrue(any(f["source"] == "custom-horizon" for f in message.content.analysis["findings"]))
