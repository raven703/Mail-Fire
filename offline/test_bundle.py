"""Dependency-free safety checks for a generated staging directory."""
import json
import unittest
from pathlib import Path

STAGE = Path(__file__).resolve().parents[1] / "dist/MICE-offline-linux-amd64"


@unittest.skipUnless(STAGE.exists(), "Build the distribution first")
class BundleTests(unittest.TestCase):
    def test_compose_is_portable_and_never_builds(self):
        config = json.loads((STAGE / "compose.offline.json").read_text())
        self.assertNotIn("/home/", json.dumps(config))
        for name, service in config["services"].items():
            self.assertNotIn("build", service)
            self.assertNotIn("container_name", service)
            self.assertEqual(service["pull_policy"], "never")
            if name != "frontend":
                self.assertNotIn("ports", service)
        for name, network in config["networks"].items():
            if name != "edge":
                self.assertTrue(network["internal"])

    def test_only_allowed_database_models(self):
        allowed = {"category", "categoryrule", "policy", "setting", "mlmodel", "inferenceartifact"}
        for obj in json.loads((STAGE / "config.json").read_text()):
            self.assertIn(obj["model"], {"records." + name for name in allowed})
            if obj["model"] == "records.category":
                self.assertIsNone(obj["fields"]["reference"])

    def test_no_host_secrets_or_training_reports(self):
        self.assertFalse((STAGE / ".env").exists())
        self.assertFalse(list((STAGE / "models").rglob("training.json")))
        self.assertFalse((STAGE / "models/horizon/training").exists())
        self.assertFalse((STAGE / "models/horizon/eval").exists())
        for name in ("install", "start", "stop", "verify"):
            self.assertTrue((STAGE / (name + ".sh")).stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()