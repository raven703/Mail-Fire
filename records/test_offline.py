import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from scripts.native_offline import verify


class OfflineTests(SimpleTestCase):
    def test_checksums_without_docker_or_services(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "image.tar").write_bytes(b"image")
            manifest = {"schema_version": 1, "images": [], "files": {"image.tar": hashlib.sha256(b"image").hexdigest()}}
            (root / "manifest.json").write_text(json.dumps(manifest))
            verify(root)
            (root / "image.tar").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify(root)

    def test_rejects_escaping_filename(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({"schema_version": 1, "images": [], "files": {"../file": "digest"}}))
            with self.assertRaises(ValueError):
                verify(root)