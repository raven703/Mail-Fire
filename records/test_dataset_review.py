from unittest.mock import patch

from django.test import SimpleTestCase

from records.datasets import ExampleReviewForm


class DatasetReviewTests(SimpleTestCase):
    def form(self, values):
        with patch("records.datasets.Category.objects") as categories:
            categories.filter.return_value.order_by.return_value.values_list.return_value = [("SECRET", "Secret")]
            return ExampleReviewForm(values)

    def test_review_requires_valid_noncontradictory_labels(self):
        for labels in ([], ["UNKNOWN"], ["NORMAL", "SECRET"]):
            self.assertFalse(self.form({"labels": labels}).is_valid())
        form = self.form({"labels": ["SECRET"], "approved": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data["approved"])

    def test_normal_can_be_saved_without_approval(self):
        form = self.form({"labels": ["NORMAL"]})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["approved"])