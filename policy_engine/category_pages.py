"""Native category/rule editing, sharing the original rule validators."""

import json
from uuid import uuid4

from django import forms
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from policy_engine.rule_forms import StructuredRuleForm as RuleForm
from records.models import Audit, Category, CategoryRule


class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        if kwargs.get("instance") is None:
            kwargs["instance"] = Category(mode="custom", group_name="Конфиденциальные данные")
        super().__init__(*args, **kwargs)

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


CategoryRules = modelformset_factory(
    CategoryRule, form=RuleForm, extra=1, can_delete=True, min_num=1,
    validate_min=True, max_num=30, validate_max=True, absolute_max=35,
)


def category_rules(data, category=None, *, prefix="rules"):
    rows = CategoryRule.objects.filter(category=category) if category and category.pk else CategoryRule.objects.none()
    return CategoryRules(data, queryset=rows.order_by("priority", "pk"), prefix=prefix)


@transaction.atomic
def save_category(actor, form, rules):
    row = form.save(commit=False)
    if row.pk:
        current = Category.objects.select_for_update().get(pk=row.pk)
        if current.mode in {"builtin", "label"}:
            raise ValueError("Системные категории нельзя изменять")
    else:
        row.pk = "CUSTOM_" + uuid4().hex
    row.save()
    if rules is not None:
        instances = rules.save(commit=False)
        for deleted in rules.deleted_objects:
            deleted.delete()
        for rule in instances:
            rule.category = row
            rule.save()
    Audit.objects.create(actor=actor.pk, action="category_update", target=row.pk)
    return row


@require_http_methods(["GET", "POST"])
def categories(request, category_id=None, rule_id=None):
    if not request.user.is_authenticated:
        return redirect("login-page")
    admin = request.user.has_perm("identity.administer")
    if not request.user.has_perm("identity.access_mice") or (request.method == "POST" and not admin):
        return HttpResponseForbidden("Недостаточно прав")
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    rule = get_object_or_404(CategoryRule, pk=rule_id, category=category) if rule_id else None
    system = category and category.mode in {"builtin", "label"}
    data = request.POST if request.method == "POST" else None
    action = data.get("action", "save") if data is not None else ""
    editing_rule = bool(rule or request.GET.get("rule") == "new" or (data and data.get("entity") == "rule"))
    editing = admin and (editing_rule or action == "save" or request.GET.get("new") == "1" or request.GET.get("edit") == "1")
    form = rules_form = None
    if request.method == "POST" and system:
        return HttpResponseForbidden("Системные категории нельзя изменять")
    if action == "archive" and category:
        with transaction.atomic():
            category = Category.objects.select_for_update().get(pk=category.pk)
            category.active = False
            category.save(update_fields=["active"])
            Audit.objects.create(actor=request.user.pk, action="category_archive", target=category.pk)
        return redirect("categories-page")
    if editing and not system:
        if editing_rule:
            if not category:
                return HttpResponseForbidden("Правила недоступны для этой категории")
            form = RuleForm(data, instance=rule)
            if data is not None and form.is_valid():
                with transaction.atomic():
                    current = Category.objects.select_for_update().get(pk=category.pk)
                    item = form.save(commit=False)
                    item.category = current
                    item.save()
                    Audit.objects.create(actor=request.user.pk, action="rule_update", target=item.pk)
                return redirect("category-detail", category_id=category.pk)
        else:
            form = CategoryForm(data, instance=category)
            rules_form = category_rules(data, category)
            if data is not None and form.is_valid():
                needs_rules = form.cleaned_data["mode"] in {"custom", "rules"}
                if not needs_rules or rules_form.is_valid():
                    row = save_category(request.user, form, rules_form if needs_rules else None)
                    return redirect("category-detail", category_id=row.pk)
    kind = request.GET.get("kind", "custom")
    query = request.GET.get("q", "").strip()[:200]
    rows = Category.objects.order_by("group_name", "name")
    if kind == "system":
        rows = rows.filter(mode__in=["builtin", "label"])
    elif kind != "all":
        rows = rows.exclude(mode__in=["builtin", "label"])
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(group_name__icontains=query) | Q(pk__icontains=query))
    return render(request, "policy_engine/categories.html", {
        "categories": rows, "category": category, "system": system, "admin": admin, "kind": kind, "query": query,
        "rules": CategoryRule.objects.filter(category=category).order_by("priority", "created_at") if category else [],
        "form": form, "rules_form": rules_form, "editing_rule": editing_rule,
    }, status=400 if data is not None else 200)


@require_http_methods(["GET", "POST"])
def category_picker_add(request):
    if not request.user.is_authenticated or not request.user.has_perm("identity.administer"):
        return HttpResponseForbidden("Недостаточно прав")
    if request.headers.get("HX-Request") != "true":
        return redirect("/categories/?new=1")
    data = request.POST if request.method == "POST" else None
    form = CategoryForm(data)
    rules = category_rules(data)
    if data is not None and form.is_valid():
        needs_rules = form.cleaned_data["mode"] in {"custom", "rules"}
        if not needs_rules or rules.is_valid():
            row = save_category(request.user, form, rules if needs_rules else None)
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({"mice:category-created": {"id": row.pk, "name": row.name,
                                                                         "group": row.group_name}})
            return response
    return render(request, "policy_engine/_picker_create_dialog.html", {"form": form, "rules_form": rules},
                  status=400 if data is not None else 200)
