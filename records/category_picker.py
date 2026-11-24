"""Grouped native category selection shared by policies and training dialogs."""

from collections import defaultdict

from django import forms
from django.template.loader import render_to_string

from records.models import Category, CategoryRule

RULE_KINDS = {"keywords": "Ключевые слова", "regex": "Regex", "reference": "Эталон", "ml": "ML"}


class CategoryPicker(forms.CheckboxSelectMultiple):
    template_name = "records/_category_picker.html"

    def __init__(self, *, policy=False, edit_options=False, selected=()):
        super().__init__()
        self.policy = policy
        self.edit_options = edit_options
        self.details = {}
        groups = defaultdict(list)
        categories = Category.objects.filter(active=True).order_by("group_name", "name")
        if policy:
            categories = categories.exclude(mode="label")
        rows = list(categories.values_list("pk", "name", "group_name", "mode"))
        modes = {pk: mode for pk, _, _, mode in rows}
        rules = defaultdict(set)
        for pk, kind in CategoryRule.objects.filter(category_id__in=modes).values_list("category_id", "kind"):
            rules[pk].add(RULE_KINDS.get(kind, kind))
        for pk, name, group, mode in rows:
            groups[group].append((pk, name))
            self.details[pk] = {
                "description": "Системный детектор" if mode == "builtin" else "Учебная категория" if mode == "label"
                else " · ".join(sorted(rules[pk])) or "Правила обнаружения",
                "editable": mode not in {"builtin", "label"},
            }
        for pk in dict.fromkeys(selected):
            if pk not in modes:
                groups["Недоступные категории"].append((pk, pk))
        self.choices = list(groups.items())

    def render(self, name, value, attrs=None, renderer=None):
        return render_to_string(self.template_name, self.get_context(name, value, attrs))

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(policy=self.policy, edit_options=self.edit_options)
        for _, options, _ in context["widget"]["optgroups"]:
            for option in options:
                option.update(self.details.get(str(option["value"]), {}))
        return context


class LabelForm(forms.Form):
    labels = forms.MultipleChoiceField(label="Категории")
    approved = forms.BooleanField(required=False, label="Разметка проверена аналитиком")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["labels"]
        field.widget = CategoryPicker()
        field.choices = field.widget.choices

    def clean_labels(self):
        labels = sorted(set(self.cleaned_data["labels"]))
        if not 1 <= len(labels) <= 20:
            raise forms.ValidationError("Выберите от 1 до 20 категорий")
        if "NORMAL" in labels and len(labels) != 1:
            raise forms.ValidationError("NORMAL нельзя совмещать с категориями")
        return labels
