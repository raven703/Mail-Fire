from django.test import SimpleTestCase

from records.datasets import DatasetImportForm
from records.operations import ConfigurationForm


class ConfigurationTests(SimpleTestCase):
    def form(self, destination):
        return ConfigurationForm({"sensitivity": "medium", "destinations": destination})

    def test_integrations_allow_explicit_internal_destinations(self):
        form = self.form("https://siem.internal/events\ncef://192.0.2.5:514")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["destinations"]), 2)

    def test_unsafe_destinations_are_rejected(self):
        for destination in ("file:///etc/passwd", "http://user:password@host/", "https://host/#secret", "http://host:99999", "http://host/\tbad"):
            with self.subTest(destination=destination):
                self.assertFalse(self.form(destination).is_valid())

    def test_dataset_form_requires_bounded_supported_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        form = DatasetImportForm({"name": "Dataset"}, {"file": SimpleUploadedFile("x.exe", b"data")})
        self.assertFalse(form.is_valid())