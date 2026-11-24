from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from policy_engine.catalog_service import PolicyError, mutate, public
from records.models import Audit, Category, Policy


@require_http_methods(["GET", "POST"])
def catalog(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    admin = request.user.has_perm("identity.administer")
    if not request.user.has_perm("identity.access_mice") or (request.method == "POST" and not admin):
        return render(request, "identity/access.html", status=403)
    editing, error = None, ""
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
            if action not in {"save", "archive", "restore", "delete"}:
                raise PolicyError("Неизвестное действие")
            if action != "save" and not request.POST.get("id"):
                raise PolicyError("Политика не найдена", 404)
            if action == "save":
                for key in ("priority", "min_risk", "min_count"):
                    body[key] = int(request.POST.get(key, ""))
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
