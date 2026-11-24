import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from policy_engine.catalog_service import PolicyError, mutate, public
from records.models import Audit, Policy


@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def policies(request, policy_id=None, action=None):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    if request.method == "GET":
        if not request.user.has_perm("identity.access_mice"):
            return JsonResponse({"detail": "Недостаточно прав"}, status=403)
        if action == "history" and policy_id:
            rows = Audit.objects.filter(target=policy_id, action="policy_save").order_by("-created_at")[:100]
            return JsonResponse(
                {
                    "items": [
                        {
                            "id": r.pk,
                            "created_at": r.created_at.isoformat(),
                            "actor": r.actor,
                            "action": r.action,
                            "target": r.target,
                            "details": r.details,
                        }
                        for r in rows
                    ]
                }
            )
        if policy_id or action:
            return JsonResponse({"detail": "Метод не поддерживается"}, status=405)
        rows = Policy.objects.order_by("priority", "name")
        if request.GET.get("include_archived", "false").lower() != "true":
            rows = rows.filter(archived=False)
        return JsonResponse({"items": [public(r) for r in rows]})
    if not request.user.has_perm("identity.administer"):
        return JsonResponse({"detail": "Требуется администратор"}, status=403)
    allowed = (
        (request.method == "POST" and policy_id is None and action is None)
        or (request.method == "PUT" and policy_id and action in {None, "enabled"})
        or (request.method == "DELETE" and policy_id and action is None)
        or (request.method == "POST" and policy_id and action in {"archive", "restore"})
    )
    if not allowed:
        return JsonResponse({"detail": "Метод не поддерживается"}, status=405)
    try:
        body = json.loads(request.body) if request.body else {}
        result = mutate(request.user, body, policy_id, "delete" if request.method == "DELETE" else action)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Некорректный JSON"}, status=400)
    except PolicyError as exc:
        return JsonResponse({"detail": str(exc)}, status=exc.status)
    return JsonResponse(result)
