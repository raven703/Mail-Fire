from unittest.mock import patch

from django.test import SimpleTestCase

from records.category_picker import LabelForm


class DatasetReviewTests(SimpleTestCase):
    def form(self, values):
        with (patch("records.category_picker.Category.objects") as categories,
              patch("records.category_picker.CategoryRule.objects")):
            categories.filter.return_value.order_by.return_value.values_list.return_value = [("NORMAL", "Безопасный материал", "ML", "label"), ("SECRET", "Secret", "DLP", "builtin")]
            return LabelForm(values)

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

    def test_review_picker_renders_named_controls(self):
        html = str(self.form({"labels": ["SECRET"]})["labels"])
        self.assertIn('data-category-picker', html)
        self.assertIn('name="labels" value="SECRET"', html)
        self.assertIn('checked', html)
