import hashlib
import io
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from scripts.native_offline import restore_local_models, verify


class OfflineTests(SimpleTestCase):
    def test_safe_model_restore_and_refusal_to_overwrite(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "models.tar"
            with tarfile.open(archive, "w") as output:
                for name in ("rubert/config.json", "setfit/modules.json"):
                    member = tarfile.TarInfo(name)
                    member.size = 2
                    output.addfile(member, io.BytesIO(b"{}"))
            restore_local_models(archive, root / "models")
            self.assertEqual((root / "models/rubert/config.json").read_bytes(), b"{}")
            with self.assertRaises(ValueError):
                restore_local_models(archive, root / "models")

    def test_rejects_model_archive_links(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "models.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo("rubert/link")
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                output.addfile(member)
            with self.assertRaises(ValueError):
                restore_local_models(archive, root / "models")
            self.assertFalse((root / "models").exists())

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