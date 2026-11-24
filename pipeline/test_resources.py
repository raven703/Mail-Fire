from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pipeline.resources import gpu_snapshot


class ResourceProbeTests(SimpleTestCase):
    def test_gpu_csv_and_unavailable_state(self):
        with patch("pipeline.resources.subprocess.run", return_value=SimpleNamespace(stdout="0, Test GPU, 35, 128, 4096, 42\n")):
            sample = gpu_snapshot()
            self.assertTrue(sample["available"])
            self.assertEqual(sample["items"][0]["used_mib"], 128)
        with patch("pipeline.resources.subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(gpu_snapshot()["available"])