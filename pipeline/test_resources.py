from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from pipeline.resource_history import resource_history
from pipeline.resources import cpu_usage, decode_probe


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

    def probe(self, when, cpu_usec=10_000_000, instance="container-1", extra=""):
        return (
            f"at {int(when.timestamp())}\ninstance {instance}\nstate running\n"
            f"cpu_usec {cpu_usec}\ncpu_quota 50000\ncpu_period 100000\n"
            f"memory.current 1024\nmemory.max max\n{extra}"
        ).encode()

    def test_probe_decodes_gpu_and_unlimited_memory(self):
        now = datetime.now(timezone.utc)
        _, values = decode_probe(self.probe(now, extra="gpu 0, Test GPU, 35, 128, 4096, 42\n"), now)
        self.assertEqual(values["gpu"][0]["used_mib"], 128)
        self.assertIsNone(values["ram_total"])
        self.assertEqual(decode_probe(self.probe(now), now)[1]["gpu"], [])

    def test_cpu_uses_cgroup_delta_and_rejects_other_instances(self):
        now = datetime.now(timezone.utc)
        older = now - timedelta(seconds=30)
        previous = decode_probe(self.probe(older), now)[1]
        current = decode_probe(self.probe(now, cpu_usec=17_500_000), now)[1]
        self.assertEqual(cpu_usage(current, previous), 50)
        self.assertIsNone(cpu_usage({**current, "instance": "container-2"}, previous))

    def test_probe_rejects_invalid_or_stale_data(self):
        now = datetime.now(timezone.utc)
        for payload in (self.probe(now - timedelta(minutes=2)), self.probe(now, instance="../host")):
            with self.assertRaises(ValueError):
                decode_probe(payload, now)

    def test_probe_matches_naive_utc_storage(self):
        aware = datetime.now(timezone.utc)
        naive = aware.replace(tzinfo=None)
        recorded, values = decode_probe(self.probe(aware), naive)
        self.assertEqual(recorded, naive.replace(microsecond=0))
        self.assertEqual(values["sample_at"], int(aware.timestamp()))
