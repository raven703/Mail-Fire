from unittest.mock import patch
from django.test import SimpleTestCase
from records.detectors import SemanticForm
from pipeline.semantic_detection import threshold


class SemanticSettingsTests(SimpleTestCase):
    def test_threshold_precedence(self):
        with patch.dict("os.environ", {"MICE_SEMANTIC_THRESHOLD": ".85"}):
            self.assertEqual(threshold(), .85)
            self.assertEqual(threshold({"threshold": .91}), .91)

    def test_threshold_form(self):
        self.assertTrue(SemanticForm({"enabled": "on", "threshold": ".85"}).is_valid())
        for invalid in ("0", "1.1", "nan", "inf"):
            self.assertFalse(SemanticForm({"threshold": invalid}).is_valid())
