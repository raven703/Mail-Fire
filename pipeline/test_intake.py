import asyncio
import base64
import io
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from pipeline.bundles import expand_bundle
from pipeline.directory import scan
from pipeline.smtp import Collector


class DirectoryTests(SimpleTestCase):
    def test_stability_idempotent_scan_and_read_only_source(self):
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.directory.accept") as accept:
            path = Path(directory) / "mail.eml"
            path.write_bytes(b"Subject: test\r\n\r\nbody")
            observed = {}
            self.assertEqual(scan(directory, observed, namespace="test", now=0)["waiting"], 1)
            self.assertEqual(scan(directory, observed, namespace="test", now=6)["accepted"], 1)
            self.assertEqual(scan(directory, observed, namespace="test", now=12)["accepted"], 0)
            accept.assert_called_once()
            self.assertTrue(path.exists())
            first_key = accept.call_args.args[2]
            fresh = {}
            scan(directory, fresh, namespace="test", now=0)
            scan(directory, fresh, namespace="test", now=6)
            self.assertEqual(first_key, accept.call_args.args[2])

    def test_symlinks_and_archive_directory_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "secret.eml"
            secret.write_bytes(b"mail")
            (Path(directory) / "link.eml").symlink_to(secret)
            (Path(directory) / "nested").symlink_to(outside, target_is_directory=True)
            archived = Path(directory) / ".imported"
            archived.mkdir()
            (archived / "old.eml").write_bytes(b"old")
            with patch("pipeline.directory.accept") as accept:
                observed = {}
                scan(directory, observed, namespace="test", now=0)
                scan(directory, observed, namespace="test", now=6)
                accept.assert_not_called()


class SMTPTests(SimpleTestCase):
    def test_allowlist_and_storage_failure(self):
        collector = Collector("127.0.0.0/8")
        envelope = SimpleNamespace(original_content=b"mail", mail_from="sender@example.org", rcpt_tos=[])
        denied = SimpleNamespace(peer=("192.0.2.1", 1234))
        allowed = SimpleNamespace(peer=("127.0.0.1", 1234))
        self.assertTrue(asyncio.run(collector.handle_DATA(None, denied, envelope)).startswith("550"))
        with patch("pipeline.smtp.close_old_connections"), patch("pipeline.smtp.accept") as accept:
            self.assertEqual(asyncio.run(collector.handle_DATA(None, allowed, envelope)), "250 Stored")
            self.assertEqual(asyncio.run(collector.handle_DATA(None, allowed, envelope)), "250 Stored")
            self.assertNotEqual(accept.call_args_list[0].args[2], accept.call_args_list[1].args[2])
            accept.side_effect = OSError()
            self.assertTrue(asyncio.run(collector.handle_DATA(None, allowed, envelope)).startswith("451"))

    @override_settings(MICE_MAX_MESSAGE_BYTES=2)
    def test_size_refused_before_storage(self):
        with patch("pipeline.smtp.accept") as accept:
            result = asyncio.run(Collector("127.0.0.0/8").handle_DATA(
                None, SimpleNamespace(peer=("127.0.0.1", 1)), SimpleNamespace(original_content=b"large"),
            ))
        self.assertTrue(result.startswith("552"))
        accept.assert_not_called()


class BundleTests(SimpleTestCase):
    def test_valid_bundle_is_fenced_and_accepts_members(self):
        job = SimpleNamespace(pk="job", token="token", payload={
            "blob_sha": "hash", "name": "x.zip", "source_key": "upload:user:token",
        })
        with (
            patch("pipeline.bundles.Blob.objects.get", return_value=SimpleNamespace(data=b"zip")),
            patch("pipeline.bundles.call", return_value={"members": [["mail.eml", "bWFpbA=="]]}),
            patch("pipeline.bundles.transaction.atomic"),
            patch("pipeline.bundles.locked_current") as fence,
            patch("pipeline.bundles.accept", return_value=SimpleNamespace(message_id="message")) as accept,
            patch("pipeline.bundles.finish") as finish,
        ):
            expand_bundle(job)
        fence.assert_called_once_with("job", "token")
        self.assertEqual(accept.call_args.args[0], b"mail")
        finish.assert_called_once_with("job", "token", {"message_ids": ["message"], "accepted": 1})

    def test_unsafe_parser_output_refused_before_writes(self):
        job = SimpleNamespace(payload={"blob_sha": "hash", "name": "x.zip"})
        with (
            patch("pipeline.bundles.Blob.objects.get", return_value=SimpleNamespace(data=b"zip")),
            patch("pipeline.bundles.call", return_value={"members": [["../escape.eml", base64.b64encode(b"x").decode()]]}),
            patch("pipeline.bundles.accept") as accept,
        ):
            with self.assertRaises(ValueError):
                expand_bundle(job)
            accept.assert_not_called()

    def test_existing_zip_algorithm_limits_and_duplicate_paths(self):
        from app.uploads import upload_members

        limits = SimpleNamespace(max_message_bytes=100000, max_objects=5, max_expanded_bytes=100000)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("nested/mail.eml", b"mail")
        self.assertEqual(upload_members(stream.getvalue(), "x.zip", limits=limits), [("nested/mail.eml", b"mail")])
        with zipfile.ZipFile(stream, "a") as archive:
            archive.writestr("../bad.eml", b"mail")
        with self.assertRaises(ValueError):
            upload_members(stream.getvalue(), "x.zip", limits=limits)