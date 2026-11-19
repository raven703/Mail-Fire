"""Versioned, reviewable DLP categories/policies: dry-run first, explicit apply.

Never auto-load rulepacks at startup. Only custom categories are managed;
built-in category IDs are immutable. Rulepacks contain no ML weights or emails.
"""
import json
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, func, select, text

from app.categories import safe_regex
from app.categories_api import CategoryBody, rule_config
from app.models import Audit, Category, CategoryRule, Policy
from app.workspace_api import PolicyBody


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CategorySpec(StrictModel):
    id: str = Field(pattern=r"^(?:pack-[a-z0-9][a-z0-9-]{2,58}|custom-[a-f0-9]{32})$", max_length=64)
    name: str = Field(min_length=2, max_length=160)
    group_name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    active: bool = True
    match_mode: str = Field(default="any", pattern=r"^(any|all)$")
    rules: list[dict] = Field(min_length=1, max_length=30)


class PolicySpec(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    enabled: bool = False
    shadow: bool = False
    priority: int = Field(default=100, ge=0, le=10000)
    min_risk: int = Field(default=40, ge=0, le=100)
    min_count: int = Field(default=1, ge=1, le=1000)
    category_match: str = Field(default="any", pattern=r"^(any|all)$")
    categories: list[str] = Field(default_factory=list, max_length=50)
    direction: list[str] = Field(default_factory=list, max_length=4)
    senders: list[str] = Field(default_factory=list, max_length=200)


class Rulepack(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    categories: list[CategorySpec] = Field(default_factory=list, max_length=100)
    policies: list[PolicySpec] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        ids = [c.id for c in self.categories]
        names = [c.name.casefold() for c in self.categories]
        policies = [p.name.casefold() for p in self.policies]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("Повторные id/названия категорий в наборе")
        if len(policies) != len(set(policies)):
            raise ValueError("Повторные названия политик в наборе")
        return self


def load_pack(filename):
    if str(filename) == "-":
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
    else:
        path = Path(filename)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("Набор правил не может превышать 1 МиБ")
        raw = path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError("Набор правил не может превышать 1 МиБ")
    return Rulepack.model_validate(json.loads(raw.decode("utf-8")))


def _rule_validated(rule):
    """Validate all fields and types using the same live category API schema."""
    from app.categories_api import RuleBody

    unknown = set(rule) - set(RuleBody.model_fields)
    if unknown:
        raise ValueError(f"Неизвестные поля правила: {sorted(unknown)}")
    body = RuleBody.model_validate(rule)
    if body.kind == "regex":
        safe_regex(body.pattern)
    return body


def inspect_pack(session, pack, *, update_existing=False):
    """Pure read-only validation & change planning. Fails closed on ambiguity."""
    existing = {x.id: x for x in session.scalars(select(Category))}
    existing_names = {x.name.casefold(): x.id for x in existing.values()}
    all_policies = list(session.scalars(select(Policy)))
    policies_by_name = {}
    for policy in all_policies:
        policies_by_name.setdefault(policy.name.casefold(), []).append(policy)
    changes = {"categories": [], "policies": []}
    # A disabled category in an incoming update may NOT be referenced by a policy.
    available = {ident for ident, category in existing.items() if category.active and category.mode != "label"}
    known = {ident for ident, category in existing.items() if category.mode != "label"}
    for cat in pack.categories:
        known.add(cat.id)
        if update_existing or cat.id not in existing:
            if cat.active:
                available.add(cat.id)
            else:
                available.discard(cat.id)
    for cat in pack.categories:
        validated = CategoryBody.model_validate(cat.model_dump(exclude={"id"}))
        if not validated.rules:
            raise ValueError(f"Нет правил: {cat.id}")
        for raw in cat.rules:
            rule_config(_rule_validated(raw), session)
        conflict = existing_names.get(cat.name.casefold())
        if conflict and conflict != cat.id:
            raise ValueError(f"Название категории уже занято другим ID: {cat.name}")
        current = existing.get(cat.id)
        if current and current.mode != "custom":
            raise ValueError(f"Нельзя переписать системную категорию: {cat.id}")
        if current and update_existing:
            owned = session.scalar(select(Audit.id).where(
                Audit.target == cat.id,
                Audit.action.in_(["rulepack_category_create", "rulepack_category_update"]),
                Audit.details["pack"].astext == pack.name,
            ).limit(1))
            if not owned:
                raise ValueError(f"Категория принадлежит другому набору: {cat.id}")
        action = "create" if not current else "update" if update_existing else "skip"
        changes["categories"].append({"id": cat.id, "name": cat.name, "action": action})
    for pol in pack.policies:
        body = PolicyBody.model_validate(pol.model_dump())
        if body.category_match == "all" and not body.categories:
            raise ValueError(f"Набор категорий для ALL пуст: {pol.name}")
        if len(body.categories) != len(set(body.categories)):
            raise ValueError(f"Дубликаты категорий в политике: {pol.name}")
        # Disabled policies may preserve references to archived categories for
        # roundtrip backup; enabling them still requires active categories.
        missing = set(body.categories) - (available if body.enabled else known)
        if missing:
            raise ValueError(f"Политика {pol.name}: нет активных категорий {sorted(missing)}")
        if any(direction not in {"INBOUND", "OUTBOUND", "INTERNAL", "UNKNOWN"} for direction in body.direction):
            raise ValueError(f"Неизвестное направление: {pol.name}")
        found = policies_by_name.get(pol.name.casefold(), [])
        if len(found) > 1:
            raise ValueError(f"Несколько существующих политик с именем {pol.name}; разрешите конфликт вручную")
        if found and update_existing:
            owned = session.scalar(select(Audit.id).where(
                Audit.target == found[0].id,
                Audit.action.in_(["rulepack_policy_create", "rulepack_policy_update"]),
                Audit.details["pack"].astext == pack.name,
            ).limit(1))
            if not owned:
                raise ValueError(f"Политика принадлежит другому набору: {pol.name}")
        action = "create" if not found else "update" if update_existing else "skip"
        changes["policies"].append({"name": pol.name, "action": action, "enabled_after": False if action != "skip" else found[0].enabled})
    return changes


def apply_pack(session, pack, actor, *, update_existing=False):
    """One transaction controlled by caller; never commits, deletes or reevaluates."""
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext('rulepack-apply'))"))
    changes = inspect_pack(session, pack, update_existing=update_existing)
    for spec, change in zip(pack.categories, changes["categories"]):
        if change["action"] == "skip":
            continue
        category = session.get(Category, spec.id, with_for_update=True)
        before = {"name": category.name, "active": category.active} if category else None
        if category is None:
            category = Category(id=spec.id, name=spec.name, mode="custom", keywords=[], reference_id=None)
            session.add(category)
            session.flush()
        category.name = spec.name
        category.group_name = spec.group_name
        category.description = spec.description
        category.active = spec.active
        category.match_mode = spec.match_mode
        session.execute(delete(CategoryRule).where(CategoryRule.category_id == category.id))
        for raw in spec.rules:
            body = _rule_validated(raw)
            config = rule_config(body, session)
            session.add(CategoryRule(
                category_id=category.id,
                kind=body.kind,
                title=body.title.strip(),
                enabled=body.enabled,
                risk=body.risk,
                priority=body.priority,
                config=config,
            ))
        session.add(Audit(
            actor=actor, action="rulepack_category_" + change["action"], target=category.id,
            details={"pack": pack.name, "before": before, "after_name": category.name},
        ))
    session.flush()
    for spec, change in zip(pack.policies, changes["policies"]):
        if change["action"] == "skip":
            continue
        row = session.scalar(select(Policy).where(func.lower(Policy.name) == spec.name.casefold()).with_for_update())
        before = {"name": row.name, "conditions": row.conditions} if row else None
        if row is None:
            row = Policy(version=0)
            session.add(row)
        row.name = spec.name
        row.enabled = False
        row.shadow = spec.shadow
        row.priority = spec.priority
        row.conditions = {**(row.conditions or {}), **spec.model_dump(include={
            "min_risk", "min_count", "category_match", "categories", "direction", "senders"
        })}
        row.version = (row.version or 0) + 1
        session.flush()
        session.add(Audit(
            actor=actor, action="rulepack_policy_" + change["action"], target=row.id,
            details={"pack": pack.name, "before": before, "version": row.version},
        ))
    return changes


def export_pack(session, name="mailfire-export"):
    """Export custom categories and policies without training data or secrets."""
    from app.categories_api import all_rows

    cats = [
        CategorySpec.model_validate({
            "id": row["id"], "name": row["name"],
            "group_name": row["group_name"], "description": row["description"],
            "active": row["active"], "match_mode": row["match_mode"],
            "rules": [{
                field: val for field, val in rule.items() if field != "id"
            } for rule in row["rules"]],
        })
        for row in all_rows(session) if row["mode"] == "custom" and (row["id"].startswith("pack-") or row["id"].startswith("custom-"))
    ]
    cats_ids = {c.id for c in cats}
    builtin_ids = set(session.scalars(select(Category.id).where(Category.mode == "builtin")))
    policies = []
    for row in session.scalars(select(Policy).order_by(Policy.name)):
        fields = row.conditions or {}
        categories = fields.get("categories", [])
        # Built-in category IDs are present on any matching Mail-Fire install.
        # Avoid exporting policies referring to missing or nonportable custom IDs.
        if any(cat not in cats_ids and cat not in builtin_ids for cat in categories):
            continue
        policies.append(PolicySpec.model_validate({
            "name": row.name, "enabled": row.enabled, "shadow": row.shadow,
            "priority": row.priority, **{key: value for key, value in fields.items() if key in PolicySpec.model_fields},
        }))
    return Rulepack(schema_version=1, name=name, categories=cats, policies=policies)
