
from django.test import SimpleTestCase

from records.category_picker import LabelForm


class LabelFormTests(SimpleTestCase):
    def test_label_limit_and_deduplication_without_db(self):
        form = object.__new__(LabelForm)
        form.cleaned_data = {"labels": ["A", "A", "B"]}
        self.assertEqual(form.clean_labels(), ["A", "B"])
        form.cleaned_data = {"labels": [str(index) for index in range(21)]}
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            form.clean_labels()
