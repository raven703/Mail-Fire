from uuid import uuid4

from django.forms import modelformset_factory
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from policy_engine.catalog_service import PolicyError, mutate, public
from policy_engine.category_pages import CategoryForm, RuleForm
from records.models import Audit, Category, CategoryRule, Policy


@require_http_methods(["GET", "POST"])
def catalog(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    admin = request.user.has_perm("identity.administer")
    if not request.user.has_perm("identity.access_mice") or (request.method == "POST" and not admin):
        return render(request, "identity/access.html", status=403)
    editing, error = None, ""
    category_form = CategoryForm(prefix="nested_category")
    # Nested fields are validated only by the create-category action, not by
    # browser validation of the surrounding policy form.
    category_form.use_required_attribute = False
    nested_category = None
    nested_form = None
    nested_rules = None
    if request.method == "POST":
        body = {
            "name": request.POST.get("name", ""),
            "enabled": "enabled" in request.POST,
            "shadow": "shadow" in request.POST,
            "categories": request.POST.getlist("categories"),
            "direction": request.POST.getlist("direction"),
            "category_match": request.POST.get("category_match", "any"),
            "senders": [s.strip() for s in request.POST.get("senders", "").split(",") if s.strip()],
        }
        try:
            action = request.POST.get("action", "save")
            nested_id = request.POST.get("nested_id")
            if action.startswith("edit_category:"):
                nested_id = action.partition(":")[2]
                action = "edit_category"
            nested_actions = {"edit_category", "save_category", "cancel_category"}
            if action not in {"save", "archive", "restore", "delete", "create_category"} | nested_actions:
                raise PolicyError("Неизвестное действие")
            if action not in {"save", "create_category"} | nested_actions and not request.POST.get("id"):
                raise PolicyError("Политика не найдена", 404)
            if action == "save":
                for key in ("priority", "min_risk", "min_count"):
                    body[key] = int(request.POST.get(key, ""))
            if action in nested_actions:
                editing = {**body, "id": request.POST.get("id", "")}
                for key in ("priority", "min_risk", "min_count"):
                    editing[key] = request.POST.get(key, "")
                if action != "cancel_category":
                    from django.shortcuts import get_object_or_404

                    nested_category = get_object_or_404(Category, pk=nested_id)
                    bound = request.POST if action == "save_category" else None
                    nested_form = CategoryForm(bound, instance=nested_category, prefix="existing_category")
                    nested_form.use_required_attribute = False
                    RuleSet = modelformset_factory(CategoryRule, form=RuleForm, extra=1, can_delete=True, max_num=100, validate_max=True)
                    nested_rules = RuleSet(bound, queryset=CategoryRule.objects.filter(category=nested_category).order_by("priority", "pk"), prefix="nested_rules")
                    editable_rules = nested_category.mode not in {"builtin", "label"}
                    if action == "save_category" and nested_form.is_valid() and (not editable_rules or nested_rules.is_valid()):
                        from django.db import transaction

                        with transaction.atomic():
                            Category.objects.select_for_update().get(pk=nested_category.pk)
                            nested_form.save()
                            if nested_category.mode not in {"builtin", "label"}:
                                instances = nested_rules.save(commit=False)
                                for deleted in nested_rules.deleted_objects:
                                    deleted.delete()
                                for rule in instances:
                                    rule.category = nested_category
                                    rule.save()
                            Audit.objects.create(actor=request.user.pk, action="category_update", target=nested_category.pk)
                        nested_category = nested_form = nested_rules = None
            elif action == "create_category":
                category_form = CategoryForm(request.POST, prefix="nested_category")
                category_form.use_required_attribute = False
                if category_form.is_valid():
                    from django.db import transaction

                    with transaction.atomic():
                        category = category_form.save(commit=False)
                        category.pk = "CUSTOM_" + uuid4().hex
                        category.save()
                        Audit.objects.create(actor=request.user.pk, action="category_update", target=category.pk)
                    body["categories"].append(category.pk)
                    category_form = CategoryForm(prefix="nested_category")
                    category_form.use_required_attribute = False
                editing = {**body, "id": request.POST.get("id", "")}
                for key in ("priority", "min_risk", "min_count"):
                    editing[key] = request.POST.get(key, "")
            else:
                mutate(request.user, body, request.POST.get("id") or None, None if action == "save" else action)
                return redirect("policies-page")
        except (PolicyError, ValueError) as exc:
            error = str(exc)
            editing = {**body, "id": request.POST.get("id", ""), "senders": body["senders"]}
            for key in ("priority", "min_risk", "min_count"):
                editing[key] = request.POST.get(key, "")
    elif request.GET.get("edit") and admin:
        row = Policy.objects.filter(pk=request.GET["edit"]).first()
        if row is None:
            return render(request, "identity/access.html", status=404)
        editing = {**public(row), **row.conditions}
    elif request.GET.get("new") and admin:
        editing = {
            "enabled": True,
            "priority": 10,
            "min_risk": 40,
            "min_count": 1,
            "category_match": "any",
            "categories": [],
            "direction": [],
        }
    rows = Policy.objects.order_by("priority", "name")
    if request.GET.get("archived") != "1":
        rows = rows.filter(archived=False)
    history = Audit.objects.none()
    if request.GET.get("history"):
        history = Audit.objects.filter(target=request.GET["history"], action__startswith="policy_").order_by(
            "-created_at"
        )[:100]
    return render(
        request,
        "policy_engine/catalog.html",
        {
            "policies": rows,
            "editing": editing,
            "category_form": category_form,
            "nested_category": nested_category, "nested_form": nested_form, "nested_rules": nested_rules,
            "show_editor": editing is not None,
            "error": error,
            "can_administer": admin,
            "history": history,
            "categories": Category.objects.filter(active=True).exclude(mode="label").order_by("name"),
            "directions": [
                ("INBOUND", "Входящая"),
                ("OUTBOUND", "Исходящая"),
                ("INTERNAL", "Внутренняя"),
                ("UNKNOWN", "Неизвестная"),
            ],
        },
    )
