from unittest.mock import patch

from django.test import SimpleTestCase

from records.ml_status import classify_ml_status, ml_status


class MLStatusTests(SimpleTestCase):
    def test_publication_and_gate(self):
        for total, published, gate, expected in [
            (0, 0, False, "Нет модели"),
            (0, 0, True, "Нет модели"),
            (2, 0, True, "Не опубликована"),
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
