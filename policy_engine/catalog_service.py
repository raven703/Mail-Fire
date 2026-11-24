"""Single transactional policy catalog service shared by HTTP and HTML adapters."""

from django.db import transaction

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
