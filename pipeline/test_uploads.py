from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from pipeline.forms import MessageUploadForm
from pipeline.uploads import upload_message


class UploadTests(SimpleTestCase):
    def form(self, name="sample.eml", data=b"Subject: Test\r\n\r\nBody", token=None):
        return MessageUploadForm(
            {"delivery_id": token or uuid4()},
            {"message": SimpleUploadedFile(name, data)},
        )

    def test_delivery_identity_is_stable_and_user_scoped(self):
        token = uuid4()
        first, second = self.form(token=token), self.form(token=token)
        self.assertTrue(first.is_valid())
        self.assertTrue(second.is_valid())
        self.assertEqual(first.source_key("one"), second.source_key("one"))
        self.assertNotEqual(first.source_key("one"), second.source_key("two"))

    @override_settings(MICE_MAX_MESSAGE_BYTES=10)
    def test_rejects_empty_oversized_and_unsupported_files(self):
        for name, data in [("x.eml", b""), ("x.msg", b"x" * 11), ("x.exe", b"exe")]:
            with self.subTest(name=name, length=len(data)):
                self.assertFalse(self.form(name, data).is_valid())

    def test_rejects_missing_delivery_identity(self):
        form = MessageUploadForm({}, {"message": SimpleUploadedFile("x.eml", b"mail")})
        self.assertFalse(form.is_valid())

    def test_observer_cannot_upload_or_accept(self):
        request = RequestFactory().post("/messages/upload/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: False)
        with patch("pipeline.uploads.accept") as accept:
            self.assertEqual(upload_message(request).status_code, 403)
            accept.assert_not_called()

    def test_upload_page_renders_native_form(self):
        request = RequestFactory().get("/messages/upload/")
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda permission: True)
        response = upload_message(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_anonymous_redirects_without_accepting(self):
        request = RequestFactory().post("/messages/upload/")
        request.user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(upload_message(request).status_code, 302)

    def test_success_uses_shared_accept_and_transactional_audit(self):
        token = uuid4()
        request = RequestFactory().post(
            "/messages/upload/",
            {"delivery_id": str(token), "message": SimpleUploadedFile("test.eml", b"mail")},
        )
        request.user = SimpleNamespace(pk="analyst", is_authenticated=True, has_perm=lambda permission: True)
        record = SimpleNamespace(message_id="message-one", duplicate=False)
        with (
            patch("pipeline.uploads.transaction.atomic"),
            patch("pipeline.uploads.accept", return_value=record) as accept,
            patch("pipeline.uploads.Audit.objects.create") as audit,
        ):
            response = upload_message(request)
        self.assertEqual(response.status_code, 202)
        accept.assert_called_once_with(b"mail", "upload", f"upload:analyst:{token}", "test.eml")
        audit.assert_called_once_with(actor="analyst", action="message_upload", target="message-one")
        self.assertContains(response, "message-one", status_code=202)

    def test_conflicting_delivery_does_not_report_success_or_audit(self):
        request = RequestFactory().post(
            "/messages/upload/",
            {"delivery_id": str(uuid4()), "message": SimpleUploadedFile("test.eml", b"mail")},
        )
        request.user = SimpleNamespace(pk="analyst", is_authenticated=True, has_perm=lambda permission: True)
        with (
            patch("pipeline.uploads.transaction.atomic"),
            patch("pipeline.uploads.accept", side_effect=ValueError("conflict")),
            patch("pipeline.uploads.Audit.objects.create") as audit,
        ):
            response = upload_message(request)
        self.assertEqual(response.status_code, 400)
        audit.assert_not_called()

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_csrf_is_enforced_before_acceptance(self):
        with patch("pipeline.uploads.accept") as accept:
            response = Client(enforce_csrf_checks=True).post("/messages/upload/", {})
        self.assertEqual(response.status_code, 403)
        accept.assert_not_called()

    def test_batch_keeps_valid_items_and_reports_invalid_files(self):
        token = uuid4()
        request = RequestFactory().post("/messages/upload/", {
            "delivery_id": str(token),
            "message": [SimpleUploadedFile("valid.eml", b"mail"), SimpleUploadedFile("invalid.bin", b"invalid")],
        })
        request.user = SimpleNamespace(pk="analyst", is_authenticated=True, has_perm=lambda permission: True)
        record = SimpleNamespace(message_id="message-one", duplicate=False)
        with patch("pipeline.uploads.accept_file", return_value={"record": record}) as accept:
            response = upload_message(request)
        self.assertEqual(accept.call_args.args[2], f"upload:analyst:{token}:0")
        self.assertContains(response, "message-one", status_code=202)
        self.assertContains(response, "invalid.bin", status_code=202)
