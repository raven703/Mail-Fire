"""Native category/rule editing, sharing the original rule validators."""

import json
from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.forms.models import BaseModelFormSet
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.category_catalog import CONTEXT_CATEGORIES, CONTEXT_MARKER, LEGACY_ALIASES, possible_duplicates
from policy_engine.rule_forms import BuiltinContextRuleForm, StructuredRuleForm as RuleForm
from records.models import Audit, Category, CategoryRule


class CategoryForm(forms.ModelForm):
    confirm_distinct = forms.BooleanField(required=False, label="Это другая категория, несмотря на похожее название")

    def clean_name(self):
        value = self.cleaned_data["name"]
        if self.instance.pk and Category.objects.filter(pk=self.instance.pk, name=value).exists():
            return value
        rows = list(Category.objects.filter(active=True).exclude(mode="label").values_list("pk", "name"))
        if any(name.casefold() == value.casefold() and pk != self.instance.pk for pk, name in rows):
            raise forms.ValidationError("Категория с таким названием уже существует.")
        duplicates = possible_duplicates(value, rows, self.instance.pk)
        if duplicates and not self.fields["confirm_distinct"].to_python(self.data.get(self.add_prefix("confirm_distinct"))):
            raise forms.ValidationError("Возможный дубль: " + ", ".join(name for _, name in duplicates[:5])
                + ". Используйте существующую категорию или подтвердите, что нужна другая.")
        return value

    def __init__(self, *args, **kwargs):
        if kwargs.get("instance") is None:
            kwargs["instance"] = Category(mode="custom", group_name="Конфиденциальные данные")
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        if self.instance.mode == "rules":
            self.initial["mode"] = "custom"

    class Meta:
        model = Category
        fields = ["name", "group_name", "description", "mode", "match_mode", "active"]
        widgets = {
            "mode": forms.Select(choices=[("custom", "Правила"), ("ml", "ML (выключен)")]),
            "match_mode": forms.Select(choices=[("any", "Любое правило"), ("all", "Все правила")]),
        }

    def clean_mode(self):
        value = self.cleaned_data["mode"]
        if self.instance.pk and self.instance.mode == "builtin":
            return "builtin"
        if value == "rules":
            value = "custom"
        if value not in {"custom", "ml"}:
            raise forms.ValidationError("Неизвестный режим категории")
        return value

    def clean_match_mode(self):
        value = self.cleaned_data["match_mode"]
        if value not in {"any", "all"}:
            raise forms.ValidationError("Неизвестная логика")
        return value


class CategoryRuleSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        live = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")]
        if not any(form.cleaned_data.get("enabled") for form in live):
            raise forms.ValidationError("Добавьте хотя бы одно включённое правило или отмените удаление.")


CategoryRules = modelformset_factory(
    CategoryRule, form=RuleForm, formset=CategoryRuleSet, extra=0, can_delete=True, min_num=0,
    max_num=30, validate_max=True, absolute_max=35,
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
            deleted.deleted_at = timezone.now()
            deleted.save(update_fields=["deleted_at"])
            Audit.objects.create(actor=actor.pk, action="rule_delete", target=deleted.pk,
                                 details={"category_id": row.pk, "title": deleted.title})
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
    kind = request.GET.get("kind", "all")
    if kind not in {"all", "system", "custom"}:
        kind = "all"
    query = request.GET.get("q", "").strip()[:200]
    list_filters = {key: value for key, value in (("kind", kind), ("q", query))
                    if value and (key != "kind" or value != "all")}

    def filtered_url(route, **kwargs):
        url = reverse(route, kwargs=kwargs or None)
        return url + ("?" + urlencode(list_filters) if list_filters else "")

    category_list_url = filtered_url("categories-page")
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    rule = get_object_or_404(CategoryRule, pk=rule_id, category=category) if rule_id else None
    system = category and category.mode in {"builtin", "label"}
    context_allowed = bool(category and category.mode == "builtin" and category.pk in CONTEXT_CATEGORIES)
    if category and category.pk in LEGACY_ALIASES and request.method == "GET":
        return redirect(filtered_url("category-detail", category_id=LEGACY_ALIASES[category.pk]))
    data = request.POST if request.method == "POST" else None
    action = data.get("action", "save") if data is not None else ""
    editing_rule = bool(rule or request.GET.get("rule") == "new" or (data and data.get("entity") == "rule"))
    editing = admin and (editing_rule or action == "save" or request.GET.get("new") == "1" or request.GET.get("edit") == "1")
    form = rules_form = None
    if request.method == "POST" and system and not (context_allowed and editing_rule and action in {"save", "delete_context"}):
        return HttpResponseForbidden("Встроенный детектор и метки обучения нельзя менять здесь")
    if action == "delete_context" and context_allowed:
        if request.method != "POST" or not admin or rule is None:
            return HttpResponseForbidden("Недостаточно прав")
        with transaction.atomic():
            Category.objects.select_for_update().get(pk=category.pk)
            rule = get_object_or_404(CategoryRule.objects.select_for_update(), pk=rule.pk, category=category,
                                     config__builtin_context=True)
            rule.deleted_at = timezone.now()
            rule.save(update_fields=["deleted_at"])
            Audit.objects.create(actor=request.user.pk, action="rule_delete", target=rule.pk,
                                 details={"category_id": category.pk, "title": rule.title})
        return redirect(filtered_url("category-detail", category_id=category.pk))
    if context_allowed and rule and rule.config.get(CONTEXT_MARKER) is not True:
        return HttpResponseForbidden("Историческое правило не является правилом контекста")
    if action == "archive" and category:
        with transaction.atomic():
            category = Category.objects.select_for_update().get(pk=category.pk)
            category.active = False
            category.save(update_fields=["active"])
            Audit.objects.create(actor=request.user.pk, action="category_archive", target=category.pk)
        return redirect(category_list_url)
    if editing and (not system or (context_allowed and editing_rule)):
        if editing_rule:
            if not category:
                return HttpResponseForbidden("Правила недоступны для этой категории")
            form = (BuiltinContextRuleForm if context_allowed else RuleForm)(data, instance=rule)
            if data is not None and form.is_valid():
                with transaction.atomic():
                    current = Category.objects.select_for_update().get(pk=category.pk)
                    if context_allowed:
                        if current.mode != 'builtin' or current.pk not in CONTEXT_CATEGORIES:
                            return HttpResponseForbidden('Категория изменилась')
                        if not rule and CategoryRule.objects.filter(category=current, config__builtin_context=True).count() >= 30:
                            return HttpResponse('Не более 30 правил контекста', status=400)
                    elif current.mode in {"builtin", "label"}:
                        return HttpResponseForbidden("Категория изменилась")
                    item = form.save(commit=False)
                    item.category = current
                    item.save()
                    Audit.objects.create(actor=request.user.pk, action="rule_update", target=item.pk)
                return redirect(filtered_url("category-detail", category_id=category.pk))
        else:
            form = CategoryForm(data, instance=category)
            rules_form = category_rules(data, category)
            if data is not None and form.is_valid():
                needs_rules = form.cleaned_data["mode"] in {"custom", "rules"}
                if not needs_rules or rules_form.is_valid():
                    row = save_category(request.user, form, rules_form if needs_rules else None)
                    return redirect(filtered_url("category-detail", category_id=row.pk))
    rows = Category.objects.order_by("group_name", "name")
    rows = rows.exclude(pk__in=LEGACY_ALIASES).exclude(mode="label")
    if kind == "system":
        rows = rows.filter(mode="builtin")
    elif kind == "custom":
        rows = rows.exclude(mode="builtin")
    if category and category.mode == "label":
        return redirect("/models/?tab=label")
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(group_name__icontains=query) | Q(pk__icontains=query))
    return render(request, "policy_engine/categories.html", {
        "category_list_url": category_list_url,
        "categories": rows, "category": category, "system": system, "admin": admin, "kind": kind, "query": query,
        "rules": (CategoryRule.objects.filter(category=category, config__builtin_context=True) if context_allowed else
                  CategoryRule.objects.filter(category=category)).order_by("priority", "created_at") if category else [],
        "form": form, "rules_form": rules_form, "editing_rule": editing_rule,
        "context_allowed": context_allowed,
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
        if not form.cleaned_data["active"]:
            form.add_error("active", "Для выбора в разметке категория должна быть активной")
        elif not needs_rules or rules.is_valid():
            row = save_category(request.user, form, rules if needs_rules else None)
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({"mice:category-created": {"id": row.pk, "name": row.name,
                                                                         "group": row.group_name}})
            return response
    return render(request, "policy_engine/_picker_create_dialog.html", {"form": form, "rules_form": rules},
                  status=400 if data is not None else 200)
