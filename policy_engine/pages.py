from datetime import timedelta
from uuid import uuid4

from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from pipeline.services import enqueue
from policy_engine.catalog_service import PolicyError, mutate, public
from policy_engine.category_pages import CategoryForm, category_rules, save_category
from records.category_picker import CategoryPicker
from records.models import Audit, Category, Incident, MailEvent, Policy


@transaction.atomic
def enqueue_reevaluation(request):
    ids = list(MailEvent.objects.order_by("-created_at", "-pk").values_list("message_id", flat=True)[:1000])
    if ids:
        job = enqueue("policy.reevaluate_batch", {"message_ids": list(dict.fromkeys(ids))}, "policy-batch:" + uuid4().hex)
        Audit.objects.create(actor=request.user.pk, action="policy_reevaluate", target=str(job.pk),
                             details={"events": len(ids), "messages": len(job.payload["message_ids"])})
    destination = redirect("operations")
    destination["Location"] += "?tab=jobs&queue=policy"
    return destination


def policy_cards(rows):
    week = timezone.now() - timedelta(days=7)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT hit->>'policy_id', count(*)
                       FROM incidents CROSS JOIN LATERAL jsonb_array_elements(policy_hits) AS hit
                       WHERE created_at >= %s GROUP BY hit->>'policy_id'""", [week])
        counts = dict(cursor.fetchall())
    names = dict(Category.objects.values_list("pk", "name"))
    for row in rows:
        row.hits = counts.get(row.pk, 0)
        row.category_labels = [names.get(key, key) for key in row.conditions.get("categories", [])]
    return {
        "active": sum(row.enabled and not row.archived and not row.shadow for row in rows),
        "shadow": sum(row.enabled and not row.archived and row.shadow for row in rows),
        "daily_hits": Incident.objects.filter(created_at__gte=week + timedelta(days=6)).count(),
    }


@require_http_methods(["GET", "POST"])
def catalog(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    admin = request.user.has_perm("identity.administer")
    if not request.user.has_perm("identity.access_mice") or (request.method == "POST" and not admin):
        return render(request, "identity/access.html", status=403)
    editing, error = None, ""
    nested_category = nested_form = nested_rules = None
    creating = False
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
            nested_actions = {"edit_category", "save_category", "cancel_category", "start_category", "create_category"}
            if action not in {"save", "archive", "restore", "delete", "toggle", "reevaluate"} | nested_actions:
                raise PolicyError("Неизвестное действие")
            if action == "reevaluate":
                return enqueue_reevaluation(request)
            if action not in {"save"} | nested_actions and not request.POST.get("id"):
                raise PolicyError("Политика не найдена", 404)
            if action == "save":
                for key in ("priority", "min_risk", "min_count"):
                    body[key] = int(request.POST.get(key, ""))
            if action in nested_actions:
                editing = {**body, "id": request.POST.get("id", "")}
                for key in ("priority", "min_risk", "min_count"):
                    editing[key] = request.POST.get(key, "")
                if action != "cancel_category":
                    creating = action in {"start_category", "create_category"}
                    if not creating:
                        nested_category = get_object_or_404(Category, pk=nested_id)
                        if nested_category.mode in {"builtin", "label"}:
                            raise PolicyError("Системные категории нельзя изменять")
                    bound = request.POST if action in {"create_category", "save_category"} else None
                    nested_form = CategoryForm(bound, instance=nested_category, prefix="category")
                    nested_form.use_required_attribute = False
                    nested_rules = category_rules(bound, nested_category, prefix="nested_rules")
                    if bound is not None and nested_form.is_valid():
                        needs_rules = nested_form.cleaned_data["mode"] in {"custom", "rules"}
                        if not needs_rules or nested_rules.is_valid():
                            row = save_category(request.user, nested_form, nested_rules if needs_rules else None)
                            if creating:
                                body["categories"].append(row.pk)
                            nested_category = nested_form = nested_rules = None
                            creating = False
            else:
                if action == "toggle":
                    mutate(request.user, {"enabled": request.POST.get("enabled") == "true"}, request.POST["id"], "enabled")
                else:
                    mutate(request.user, body, request.POST.get("id") or None, None if action == "save" else action)
                return redirect("policies-page")
        except (PolicyError, ValueError) as exc:
            error = str(exc)
            if action not in {"toggle", "reevaluate"}:
                editing = {**body, "id": request.POST.get("id", "")}
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
    rows = list(rows)
    history = Audit.objects.none()
    if request.GET.get("history"):
        history = Audit.objects.filter(action__startswith="policy_")
        if request.GET["history"] != "all":
            history = history.filter(target=request.GET["history"])
        history = history.order_by("-created_at")[:100]
    picker = None
    if editing is not None:
        selected = editing.get("categories", [])
        widget = CategoryPicker(policy=True, edit_options=nested_form is None, selected=selected)
        picker = widget.render("categories", selected, attrs={"id": "policy-categories"})
    return render(
        request,
        "policy_engine/catalog.html",
        {
            "policies": rows, "counts": policy_cards(rows),
            "editing": editing,
            "creating_category": creating,
            "nested_category": nested_category, "nested_form": nested_form, "nested_rules": nested_rules,
            "show_editor": editing is not None,
            "error": error,
            "can_administer": admin,
            "history": history,
            "category_picker": picker,
            "directions": [
                ("INBOUND", "Входящая"),
                ("OUTBOUND", "Исходящая"),
                ("INTERNAL", "Внутренняя"),
                ("UNKNOWN", "Неизвестная"),
            ],
        },
    )
