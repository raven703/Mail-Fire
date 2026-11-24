"""Portable rulepacks: bounded validation, review token, atomic inactive import."""

import json
import re

from django.core import signing
from django.db import connection, transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from policy_engine.catalog_service import revision
from policy_engine.rule_config import validate_config
from records.models import Audit, Category, CategoryRule, Policy, Reference
from records.operations import admin_access

LIMIT = 1024 * 1024
CONDITIONS = {"min_risk", "min_count", "category_match", "categories", "direction", "senders"}


def text(value, low, high):
    if not isinstance(value, str) or not low <= len(value.strip()) <= high:
        raise ValueError("Некорректная строка набора")
    return value.strip()


def number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Некорректное число набора")
    return value


def boolean(value):
    if type(value) is not bool:
        raise ValueError("Ожидается логическое значение")
    return value


def objects(value, limit):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(item, dict) for item in value):
        raise ValueError("Некорректный список объектов")
    return value


def strings(value, limit):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(item, str) for item in value):
        raise ValueError("Некорректный список строк")
    if len(set(value)) != len(value):
        raise ValueError("Повторные значения")
    return value


def parse(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > LIMIT:
        raise ValueError("Максимум 1 МиБ")
    pack = json.loads(raw)
    if not isinstance(pack, dict) or set(pack) - {"schema_version", "name", "description", "categories", "policies"}:
        raise ValueError("Неизвестные поля набора")
    if type(pack.get("schema_version")) is not int or pack["schema_version"] != 1:
        raise ValueError("Поддерживается schema_version=1")
    pack["name"] = text(pack.get("name"), 2, 120)
    pack["description"] = text(pack.get("description", ""), 0, 1000)
    cats = objects(pack.setdefault("categories", []), 100)
    policies = objects(pack.setdefault("policies", []), 100)
    ids, names = set(), set()
    for cat in cats:
        if set(cat) - {"id", "name", "group_name", "description", "active", "match_mode", "rules"}:
            raise ValueError("Неизвестные поля категории")
        identifier = cat.get("id", "")
        if not isinstance(identifier, str) or not re.fullmatch(r"(?:pack-[a-z0-9][a-z0-9-]{2,58}|custom-[a-f0-9]{32}|CUSTOM_[a-f0-9]{32})", identifier):
            raise ValueError("Непереносимый ID категории")
        cat["name"] = text(cat.get("name"), 2, 160)
        if identifier in ids or cat["name"].casefold() in names:
            raise ValueError("Повторные категории")
        ids.add(identifier)
        names.add(cat["name"].casefold())
        cat["group_name"] = text(cat.get("group_name"), 1, 120)
        cat["description"] = text(cat.get("description", ""), 0, 2000)
        cat["active"] = boolean(cat.get("active", True))
        cat.setdefault("match_mode", "any")
        if cat["match_mode"] not in {"any", "all"}:
            raise ValueError("Некорректная логика категории")
        rules = objects(cat.get("rules"), 30)
        if not rules:
            raise ValueError("Категория без правил")
        for rule in rules:
            metadata = {"kind", "title", "enabled", "risk", "priority"}
            allowed = metadata | {"phrases", "match_type", "terms", "min_score", "window", "ordered", "pattern", "reference_ids", "min_similarity", "min_confidence", "exclude_phrases"}
            if set(rule) - allowed:
                raise ValueError("Неизвестные поля правила")
            rule["title"] = text(rule.get("title", ""), 0, 160)
            rule["enabled"] = boolean(rule.get("enabled", True))
            rule["risk"] = number(rule.get("risk", 70), 0, 100)
            rule["priority"] = number(rule.get("priority", 100), 0, 10000)
            config = validate_config(rule.get("kind"), {key: value for key, value in rule.items() if key not in metadata})
            rule["config"] = config
    names = set()
    for policy in policies:
        if set(policy) - (CONDITIONS | {"name", "enabled", "shadow", "priority"}):
            raise ValueError("Неизвестные поля политики")
        policy["name"] = text(policy.get("name"), 2, 200)
        if policy["name"].casefold() in names:
            raise ValueError("Повторные политики")
        names.add(policy["name"].casefold())
        policy["enabled"] = boolean(policy.get("enabled", False))
        policy["shadow"] = boolean(policy.get("shadow", False))
        for key, default, low, high in [("priority", 100, 0, 10000), ("min_risk", 40, 0, 100), ("min_count", 1, 1, 1000)]:
            policy[key] = number(policy.get(key, default), low, high)
        for key, limit in [("categories", 50), ("direction", 4), ("senders", 200)]:
            policy[key] = strings(policy.get(key, []), limit)
        policy.setdefault("category_match", "any")
        if policy["category_match"] not in {"any", "all"} or (policy["category_match"] == "all" and not policy["categories"]):
            raise ValueError("Некорректная логика политики")
        if set(policy["direction"]) - {"INBOUND", "OUTBOUND", "INTERNAL", "UNKNOWN"}:
            raise ValueError("Неизвестное направление")
    return pack


def inspect(pack, update=False):
    existing = {row.pk: row for row in Category.objects.all()}
    available = {key for key, row in existing.items() if row.mode != "label"}
    active = {key for key in available if existing[key].active}
    changes = []
    for cat in pack["categories"]:
        row = existing.get(cat["id"])
        if row and row.mode not in {"custom", "rules"}:
            raise ValueError("Системную категорию менять нельзя")
        if any(other.name.casefold() == cat["name"].casefold() and other.pk != cat["id"] for other in existing.values()):
            raise ValueError("Название категории занято")
        if row and update and not Audit.objects.filter(target=row.pk, action__in=["rulepack_category_create", "rulepack_category_update"], details__pack=pack["name"]).exists():
            raise ValueError("Категория принадлежит другому набору")
        for rule in cat["rules"]:
            ids = rule["config"].get("reference_ids", [])
            if Reference.objects.filter(pk__in=ids).count() != len(ids):
                raise ValueError("Неизвестный эталон")
        available.add(cat["id"])
        if not row or update:
            active.add(cat["id"]) if cat["active"] else active.discard(cat["id"])
        changes.append({"entity": "category", "name": cat["name"], "action": "create" if not row else "update" if update else "skip"})
    for spec in pack["policies"]:
        rows = [row for row in Policy.objects.all() if row.name.casefold() == spec["name"].casefold()]
        if len(rows) > 1:
            raise ValueError("Неоднозначное имя политики")
        if set(spec["categories"]) - (active if spec["enabled"] else available):
            raise ValueError("Политика ссылается на недоступную категорию")
        if rows and update and not Audit.objects.filter(target=rows[0].pk, action__in=["rulepack_policy_create", "rulepack_policy_update"], details__pack=pack["name"]).exists():
            raise ValueError("Политика принадлежит другому набору")
        changes.append({"entity": "policy", "name": spec["name"], "action": "create" if not rows else "update" if update else "skip"})
    return changes


@transaction.atomic
def apply(pack, actor, update=False):
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE categories, category_rules, policies IN SHARE ROW EXCLUSIVE MODE")
    changes = inspect(pack, update)
    for spec, change in zip(pack["categories"], changes):
        if change["action"] == "skip":
            continue
        row, _ = Category.objects.update_or_create(pk=spec["id"], defaults={
            **{key: spec[key] for key in ("name", "group_name", "description", "active", "match_mode")},
            "mode": "custom", "keywords": [],
        })
        CategoryRule.objects.filter(category=row).delete()
        for rule in spec["rules"]:
            CategoryRule.objects.create(category=row, **{key: rule[key] for key in ("kind", "title", "enabled", "risk", "priority", "config")})
        Audit.objects.create(actor=actor.pk, action="rulepack_category_" + change["action"], target=row.pk, details={"pack": pack["name"]})
    for spec, change in zip(pack["policies"], changes[len(pack["categories"]):]):
        if change["action"] == "skip":
            continue
        row = Policy.objects.filter(name__iexact=spec["name"]).first() or Policy(version=0)
        row.name, row.enabled, row.shadow, row.priority = spec["name"], False, spec["shadow"], spec["priority"]
        row.conditions = {**(row.conditions or {}), **{key: spec[key] for key in CONDITIONS}}
        row.version += 1
        row.save()
        revision(row)
        Audit.objects.create(actor=actor.pk, action="rulepack_policy_" + change["action"], target=row.pk, details={"pack": pack["name"]})
    return changes


def export():
    categories = []
    for row in Category.objects.filter(mode__in=["custom", "rules"]).order_by("pk"):
        rules = [{"kind": rule.kind, "title": rule.title, "enabled": rule.enabled, "risk": rule.risk, "priority": rule.priority, **rule.config} for rule in CategoryRule.objects.filter(category=row).order_by("priority", "pk")]
        if rules:
            categories.append({"id": row.pk, "name": row.name, "group_name": row.group_name, "description": row.description, "active": row.active, "match_mode": row.match_mode, "rules": rules})
    ids = {cat["id"] for cat in categories} | set(Category.objects.filter(mode="builtin").values_list("pk", flat=True))
    policies = [{"name": row.name, "enabled": row.enabled, "shadow": row.shadow, "priority": row.priority, **{key: value for key, value in row.conditions.items() if key in CONDITIONS}} for row in Policy.objects.filter(archived=False).order_by("name") if not set(row.conditions.get("categories", [])) - ids]
    return {"schema_version": 1, "name": "mice-export", "categories": categories, "policies": policies}


@require_http_methods(["GET", "POST"])
def page(request):
    error = admin_access(request)
    if error is not None:
        return error
    context = {}
    if request.GET.get("export") == "1":
        response = HttpResponse(json.dumps(export(), ensure_ascii=False, indent=2), content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="mice-rulepack.json"'
        Audit.objects.create(actor=request.user.pk, action="rulepack_export", target="mice-export")
        return response
    if request.method == "POST":
        try:
            if request.POST.get("action") == "apply":
                payload = signing.loads(request.POST.get("review", ""), salt="rulepack-review", max_age=900)
                if payload["actor"] != request.user.pk:
                    raise ValueError("Чужой предпросмотр")
                context["changes"] = apply(parse(payload["raw"]), request.user, payload["update"])
                context["applied"] = True
            else:
                upload = request.FILES.get("file")
                if upload is None:
                    raise ValueError("Выберите JSON")
                data = upload.read(LIMIT + 1)
                pack = parse(data)
                raw = data.decode("utf-8")
                update = request.POST.get("update") == "1"
                context["changes"] = inspect(pack, update)
                context["review"] = signing.dumps({"actor": request.user.pk, "raw": raw, "update": update}, salt="rulepack-review", compress=True)
        except (ValueError, TypeError, KeyError, RecursionError, signing.BadSignature) as exc:
            context["error"] = str(exc)
    context["history"] = Audit.objects.filter(action__startswith="rulepack_").order_by("-created_at")[:50]
    return render(request, "policy_engine/rulepacks.html", context, status=400 if context.get("error") else 200)