from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pipeline.resource_history import resource_history
from pipeline.resources import gpu_snapshot


class ResourceProbeTests(SimpleTestCase):
    def test_history_keeps_services_separate_and_bounds_series(self):
        samples = [SimpleNamespace(service="parser", created_at=i,
                                   values={"cpu_percent": 10, "ram_used": 25, "ram_total": 100})
                   for i in range(30, 0, -1)]
        samples.append(SimpleNamespace(service="worker", created_at=1, values={}))
        history = resource_history(samples)
        self.assertEqual(len(history), 2)
        self.assertEqual(len(history[0]["rows"]), 20)
        self.assertEqual(history[0]["latest"]["ram_percent"], 25)
        self.assertEqual(history[0]["series"][0]["created_at"], 11)
        self.assertIsNone(history[1]["latest"]["ram_percent"])

    def test_gpu_csv_and_unavailable_state(self):
        with patch("pipeline.resources.subprocess.run", return_value=SimpleNamespace(stdout="0, Test GPU, 35, 128, 4096, 42\n")):
            sample = gpu_snapshot()
            self.assertTrue(sample["available"])
            self.assertEqual(sample["items"][0]["used_mib"], 128)
        with patch("pipeline.resources.subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(gpu_snapshot()["available"])