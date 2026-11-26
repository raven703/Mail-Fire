import unittest

from app.ocr_evidence import display, evidence


class OCREvidenceTests(unittest.TestCase):
    def test_states(self):
        for required, enabled, attempted, status, expected in [
            (False, True, False, "ANALYZED", "not_required"),
            (True, False, False, "PARTIAL", "skipped"),
            (True, True, False, "PARTIAL", "pending"),
            (True, True, True, "FAILED", "error"),
            (True, True, True, "PARTIAL", "unknown"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(evidence({}, status, required=required,
                                          enabled=enabled, attempted=attempted)["ocr_state"], expected)

    def test_actual_engine_and_empty(self):
        for blocks, expected in [([], "empty"), ([{"text": "test"}], "done")]:
            details = {"ocr": [{"engine": "rapidocr", "blocks": blocks}]}
            meta = evidence(details, "ANALYZED", attempted=True)
            self.assertEqual(meta["ocr_state"], expected)
            self.assertEqual(display(meta, "ANALYZED")[1], "RapidOCR")

    def test_legacy_unknown(self):
        self.assertEqual(display({}, "ANALYZED")[0], "Нет данных")
