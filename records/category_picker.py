"""Grouped native category selection shared by policies and training dialogs."""

from collections import defaultdict

from django import forms
from django.template.loader import render_to_string

from records.models import Category, CategoryRule
from app.category_catalog import LEGACY_ALIASES, detector_name

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
        selected = tuple(selected or ())
        rows = [row for row in categories.values_list("pk", "name", "group_name", "mode")
                if row[0] not in LEGACY_ALIASES or row[0] in selected]
        modes = {pk: mode for pk, _, _, mode in rows}
        rules = defaultdict(set)
        for pk, kind in CategoryRule.objects.filter(category_id__in=modes).values_list("category_id", "kind"):
            rules[pk].add(RULE_KINDS.get(kind, kind))
        for pk, name, group, mode in rows:
            groups[group].append((pk, name))
            self.details[pk] = {
                "description": (("Устаревший идентификатор → " + LEGACY_ALIASES[pk]) if pk in LEGACY_ALIASES else
                                "Встроенный детектор: " + (detector_name(pk) or name)) if mode == "builtin" else "Метка обучения" if mode == "label"
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
        field.widget = CategoryPicker(selected=self.initial.get("labels", ()))
        field.choices = field.widget.choices

    def clean_labels(self):
        labels = sorted(set(self.cleaned_data["labels"]))
        if not 1 <= len(labels) <= 20:
            raise forms.ValidationError("Выберите от 1 до 20 категорий")
        if "NORMAL" in labels and len(labels) != 1:
            raise forms.ValidationError("NORMAL нельзя совмещать с категориями")
        return labels
