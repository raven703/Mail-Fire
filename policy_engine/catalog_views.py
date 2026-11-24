import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from policy_engine.models import PolicyRevision
from policy_engine.service import digest
from records.models import Audit, Category, Incident, Policy


class PolicyError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def public(row):
    return {
        "id": row.pk,
        "name": row.name,
        "enabled": row.enabled,
        "shadow": row.shadow,
        "priority": row.priority,
        "version": row.version,
        "archived": row.archived,
        "conditions": row.conditions,
        "created_at": row.created_at.isoformat(),
    }


def validate(body):
    if not isinstance(body, dict):
        raise PolicyError("Некорректные данные")
    if not isinstance(body.get("name"), str) or not 1 <= len(body["name"]) <= 200:
        raise PolicyError("Укажите имя политики длиной до 200 символов")
    result = {"name": body["name"]}
    for key, default in [("enabled", True), ("shadow", False)]:
        result[key] = body.get(key, default)
        if type(result[key]) is not bool:
            raise PolicyError("Некорректное значение " + key)
    for key, default, low, high in [
        ("priority", 10, 0, 10000),
        ("min_risk", 40, 0, 100),
        ("min_count", 1, 1, 1000),
    ]:
        value = body.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise PolicyError("Некорректное значение " + key)
        result[key] = value
    for key, limit in [("categories", 50), ("direction", 4), ("senders", 200)]:
        value = body.get(key, [])
        if not isinstance(value, list) or len(value) > limit or any(not isinstance(v, str) for v in value):
            raise PolicyError("Некорректный список " + key)
        result[key] = value
    result["category_match"] = body.get("category_match", "any")
    if result["category_match"] not in {"any", "all"}:
        raise PolicyError("Некорректный режим категорий")
    if result["category_match"] == "all" and not result["categories"]:
        raise PolicyError("Для режима «Все категории» выберите хотя бы одну категорию")
    available = set(
        Category.objects.filter(pk__in=result["categories"], active=True)
        .exclude(mode="label")
        .values_list("pk", flat=True)
    )
    if set(result["categories"]) != available:
        raise PolicyError("Категория неизвестна, архивирована или предназначена только для ML")
    if set(result["direction"]) - {"INBOUND", "OUTBOUND", "UNKNOWN", "INTERNAL"}:
        raise PolicyError("Неизвестное направление")
    return result


def revision(row):
    snapshot = public(row)
    PolicyRevision.objects.get_or_create(
        policy_id=row.pk, version=row.version, fingerprint=digest(snapshot), defaults={"snapshot": snapshot}
    )


@transaction.atomic
def mutate(actor, body, policy_id=None, action=None):
    row = Policy.objects.select_for_update().filter(pk=policy_id).first() if policy_id else None
    if policy_id and row is None:
        raise PolicyError("Политика не найдена", 404)
    before = public(row) if row else None
    if action == "delete":
        revision(row)
        Incident.objects.filter(policy=row).update(policy=None)
        Audit.objects.create(
            actor=actor.pk, action="policy_delete", target=row.pk, details={"snapshot": before}
        )
        row.delete()
        return {"deleted": True, "id": policy_id}
    if action in {"archive", "restore"}:
        row.archived, row.enabled = action == "archive", False
        row.save(update_fields=["archived", "enabled"])
        revision(row)
        Audit.objects.create(
            actor=actor.pk, action="policy_" + action, target=row.pk, details={"snapshot": public(row)}
        )
        return {"archived": row.archived, "restored": action == "restore", "enabled": False}
    if action == "enabled":
        if not isinstance(body, dict) or type(body.get("enabled")) is not bool:
            raise PolicyError("Некорректное значение enabled")
        body = {
            **row.conditions,
            "name": row.name,
            "shadow": row.shadow,
            "priority": row.priority,
            "enabled": body["enabled"],
        }
    data = validate(body)
    row = row or Policy(version=0)
    for key in ("name", "enabled", "shadow", "priority"):
        setattr(row, key, data.pop(key))
    row.conditions = data
    row.version += 1
    row.save()
    after = public(row)
    revision(row)
    Audit.objects.create(
        actor=actor.pk, action="policy_save", target=row.pk, details={"before": before, "after": after}
    )
    return after


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
