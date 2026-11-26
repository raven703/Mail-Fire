from unittest.mock import patch

from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.urls import reverse

from records.ml_status import classify_ml_status, ml_status


class MLStatusTests(SimpleTestCase):
    def test_enabled_ui_is_not_a_health_confirmation(self):
        row = {"id": "ml", "name": "ML", "enabled": True, "status_label": "Включён",
               "inference_enabled": True, "total_count": 3, "published_count": 3,
               "published_models": [{"name": "model", "engine_label": "SetFit"}]}
        html = render_to_string("records/detectors.html", {"rows": [row], "selected": row})
        self.assertIn(reverse("models-page"), html)
        self.assertIn("SetFit", html)
        self.assertIn("Включён (конфигурация)", html)
        self.assertIn("Ошибки загрузки модели", html)
        self.assertNotIn('class="badge OK"', html)

    def test_publication_and_gate(self):
        for total, published, gate, expected in [
            (0, 0, False, "Нет модели"),
            (0, 0, True, "Нет модели"),
            (2, 0, True, "Не опубликована"),
            (2, 0, False, "Не опубликована"),
            (2, 1, False, "Отключён"),
            (2, 1, True, "Включён"),
        ]:
            with self.subTest(total=total, published=published, gate=gate):
                self.assertEqual(classify_ml_status(total, published, gate), expected)

    @patch("records.ml_status.enabled", return_value=False)
    @patch("records.ml_status.MLModel.objects")
    def test_publication_does_not_enable_inference(self, objects, gate):
        models = objects.all.return_value
        models.count.return_value = 1
        models.filter.return_value.values.return_value = [{"name": "v1", "engine": "tfidf"}]
        status = ml_status()
        self.assertTrue(status["available"])
        self.assertFalse(status["enabled"])
        self.assertEqual(status["status_label"], "Отключён")
        gate.assert_called_once_with("ml")

    @patch("records.ml_status.enabled", return_value=True)
    @patch("records.ml_status.MLModel.objects")
    def test_all_supported_engines_are_displayed_without_loading(self, objects, gate):
        models = objects.all.return_value
        models.count.return_value = 4
        models.filter.return_value.values.return_value = [
            {"name": engine, "engine": engine} for engine in ("tfidf", "setfit", "rubert")
        ]
        status = ml_status()
        self.assertEqual(status["status_label"], "Включён")
        self.assertEqual(status["total_count"], 4)
        self.assertEqual(status["published_count"], 3)
        self.assertEqual([m["engine_label"] for m in status["published_models"]],
                         ["TF-IDF / Logistic Regression", "SetFit", "RuBERT-tiny2"])
        models.filter.assert_called_once_with(active=True)
