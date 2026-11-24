"""Native category/rule editing, sharing the original rule validators."""

import json
from uuid import uuid4

from django import forms
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from records.models import Audit, Category, CategoryRule, Reference


class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.mode == "builtin":
            self.fields["mode"].widget = forms.TextInput()
            self.fields["mode"].disabled = True

    class Meta:
        model = Category
        fields = ["name", "group_name", "description", "mode", "match_mode", "active"]
        widgets = {
            "mode": forms.Select(choices=[("custom", "Правила"), ("rules", "Правила (native)"), ("label", "Метка датасета"), ("ml", "ML (выключен)")]),
            "match_mode": forms.Select(choices=[("any", "Любое правило"), ("all", "Все правила")]),
        }

    def clean_mode(self):
        value = self.cleaned_data["mode"]
        if self.instance.pk and self.instance.mode == "builtin":
            return "builtin"
        if value not in {"custom", "rules", "label", "ml"}:
            raise forms.ValidationError("Неизвестный режим категории")
        return value

    def clean_match_mode(self):
        value = self.cleaned_data["match_mode"]
        if value not in {"any", "all"}:
            raise forms.ValidationError("Неизвестная логика")
        return value


class RuleForm(forms.ModelForm):
    class Meta:
        model = CategoryRule
        fields = ["title", "kind", "risk", "priority", "enabled", "config"]
        widgets = {"kind": forms.Select(choices=[
            ("keywords", "Ключевые слова"), ("regex", "Regex"),
            ("reference", "Эталонные документы"), ("ml", "ML (выключен)"),
        ])}

    def clean_risk(self):
        value = self.cleaned_data["risk"]
        if not 0 <= value <= 100:
            raise forms.ValidationError("Риск: 0–100")
        return value

    def clean_priority(self):
        value = self.cleaned_data["priority"]
        if not 0 <= value <= 10000:
            raise forms.ValidationError("Приоритет: 0–10000")
        return value

    def clean(self):
        values = super().clean()
        config, kind = values.get("config"), values.get("kind")
        if not isinstance(config, dict) or len(json.dumps(config)) > 64000:
            self.add_error("config", "Ожидается JSON-объект до 64 КБ")
            return values
        if kind not in {"keywords", "regex", "reference", "ml"}:
            self.add_error("kind", "Неизвестный движок")
            return values
        try:
            from policy_engine.rule_config import validate_config

            values["config"] = validate_config(kind, config)
        except (ValueError, TypeError, KeyError) as exc:
            self.add_error("config", str(exc))
        if kind == "reference" and "config" in values and "config" not in self.errors:
            ids = values["config"].get("reference_ids", [])
            if Reference.objects.filter(pk__in=ids).count() != len(set(ids)):
                self.add_error("config", "Неизвестный эталон")
        return values


@require_http_methods(["GET", "POST"])
def categories(request, category_id=None, rule_id=None):
    if not request.user.is_authenticated:
        return redirect("login-page")
    if not request.user.has_perm("identity.administer"):
        return HttpResponseForbidden("Недостаточно прав")
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    rule = get_object_or_404(CategoryRule, pk=rule_id, category=category) if rule_id else None
    editing_rule = rule is not None or request.GET.get("rule") == "new" or request.POST.get("entity") == "rule"
    if editing_rule and (category is None or category.mode in {"builtin", "label"}):
        return HttpResponseForbidden("Правила недоступны для этой категории")
    form_class = RuleForm if editing_rule else CategoryForm
    form = form_class(request.POST if request.method == "POST" else None, instance=rule if editing_rule else category)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if category:
                current = Category.objects.select_for_update().get(pk=category.pk)
                if editing_rule and current.mode in {"builtin", "label"}:
                    return HttpResponseForbidden("Правила недоступны для этой категории")
            row = form.save(commit=False)
            if editing_rule:
                row.category = category
            elif not row.pk:
                row.pk = "CUSTOM_" + uuid4().hex
            row.save()
            Audit.objects.create(actor=request.user.pk, action="rule_update" if editing_rule else "category_update", target=row.pk)
        return redirect("category-detail", category_id=category.pk if editing_rule else row.pk)
    return render(request, "policy_engine/categories.html", {
        "categories": Category.objects.order_by("group_name", "name"), "category": category,
        "rules": CategoryRule.objects.filter(category=category).order_by("priority", "created_at") if category else [],
        "form": form, "editing_rule": editing_rule,
    }, status=400 if form.is_bound else 200)