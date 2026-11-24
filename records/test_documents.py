import base64
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from records.attachments import PreviewForm, attachment, findings_for, rasterize
from records.references import prepare_reference


class DocumentTests(SimpleTestCase):
    def row(self):
        return SimpleNamespace(
            name="document.pdf", text="saved evidence", blob_sha_ref=SimpleNamespace(size=5, data=b"%PDF-"),
            message=SimpleNamespace(content=SimpleNamespace(analysis={"findings": [
                {"filename": "document.pdf", "excerpt": "match"},
                {"excerpt": "saved"}, {"excerpt": "unrelated"},
            ]})),
        )

    def test_originals_denial_precedes_attachment_lookup(self):
        request = RequestFactory().get("/attachments/one/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: False)
        with patch("records.attachments.get_object_or_404") as lookup:
            self.assertEqual(attachment(request, "one").status_code, 403)
            lookup.assert_not_called()

    def test_preview_parameters_are_bounded(self):
        for page, scale in [(0, 1), (1001, 1), (1, 3), (1, "nan"), (1, "inf")]:
            with self.subTest(page=page, scale=scale):
                self.assertFalse(PreviewForm({"page": page, "scale": scale}).is_valid())

    def test_rasterization_reuses_sandbox_and_validates_png(self):
        png = b"\x89PNG\r\n\x1a\nimage"
        with patch("records.attachments.call", return_value={"image": base64.b64encode(png).decode(), "pages": 2}) as call:
            image, pages = rasterize(self.row(), {"page": 1, "scale": 1, "highlight": True})
        self.assertEqual((image, pages), (png, 2))
        self.assertEqual(call.call_args.args[0], "preview")
        with patch("records.attachments.call", return_value={"image": base64.b64encode(b"<script>").decode(), "pages": 1}):
            with self.assertRaises(ValueError):
                rasterize(self.row(), {"page": 1, "scale": 1, "highlight": False})

    def test_findings_are_scoped_to_attachment(self):
        self.assertEqual(len(findings_for(self.row())), 2)

    def test_template_does_not_retain_sample_personal_data(self):
        sample = "ИНН 7707083893 персональное имя образца"
        prepared = prepare_reference(b"sample bytes", "sample.txt", "inn_ru", {"text": sample, "status": "ANALYZED"})
        self.assertNotIn("7707083893", str(prepared))
        self.assertNotIn("персональное имя", str(prepared))
        self.assertEqual(prepared["data"], b"document-template:inn_ru")

    def test_fingerprint_and_empty_reference(self):
        prepared = prepare_reference(b"bytes", "reference.txt", "", {"text": "stable document text", "status": "ANALYZED"})
        self.assertEqual(prepared["data"], b"bytes")
        self.assertIn("sha256", prepared["fingerprint"])
        with self.assertRaises(ValueError):
            prepare_reference(b"bytes", "reference.txt", "", {"text": "", "status": "ANALYZED"})