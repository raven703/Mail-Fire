"""Category catalog with bounded, auditable multi-rule administration."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app.api import admin, db, user
from app.categories import safe_regex
from app.models import Audit, Category, CategoryRule, Reference

router = APIRouter(prefix="/api/categories", tags=["Categories"])
RuleKind = Literal["keywords", "regex", "reference", "ml"]


class RuleBody(BaseModel):
    kind: RuleKind
    title: str = Field(default="", max_length=160)
    enabled: bool = True
    risk: int = Field(default=70, ge=0, le=100)
    priority: int = Field(default=100, ge=0, le=10000)
    exclude_phrases: list[str] = Field(default_factory=list, max_length=30)
    phrases: list[str] = Field(default_factory=list, max_length=30)
    match_type: Literal["substring", "word", "morphology", "flexible"] = "substring"
    terms: list[dict] = Field(default_factory=list, max_length=30)
    min_score: int = Field(default=1, ge=1, le=1000)
    window: int = Field(default=12, ge=1, le=80)
    ordered: bool = False
    pattern: str = Field(default="", max_length=120)
    reference_ids: list[str] = Field(default_factory=list, max_length=20)
    min_similarity: float = Field(default=0.8, ge=0.5, le=1)
    min_confidence: float = Field(default=0.7, ge=0.0, le=1)


class CategoryBody(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    group_name: str = Field(default="Другое", min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    active: bool = True
    match_mode: Literal["any", "all"] = "any"
    rules: list[RuleBody] = Field(default_factory=list, max_length=30)


def present(row, rules=()):
    return {
        "id": row.id,
        "name": row.name,
        "group_name": row.group_name,
        "description": row.description,
        "active": row.active,
        "mode": row.mode,
        "match_mode": row.match_mode,
        "system": row.mode in {"builtin", "label"},
        "rules": [
            {
                "id": rule.id,
                "kind": rule.kind,
                "title": rule.title,
                "enabled": rule.enabled,
                "risk": rule.risk,
                "priority": rule.priority,
                **(rule.config or {}),
            }
            for rule in rules
        ],
    }


def all_rows(session):
    cats = list(session.scalars(select(Category).order_by(Category.group_name, Category.name)))
    rules = list(session.scalars(select(CategoryRule).order_by(CategoryRule.created_at, CategoryRule.id)))
    grouped = {}
    for rule in rules:
        grouped.setdefault(rule.category_id, []).append(rule)
    return [present(cat, grouped.get(cat.id, [])) for cat in cats]


@router.get("")
def listing(account=Depends(user), session=Depends(db)):
    return {"items": all_rows(session)}


def rule_config(body, session):
    excludes = sorted(set(x.strip() for x in body.exclude_phrases if x.strip()))
    if any(len(x) < 3 or len(x) > 120 for x in excludes):
        raise HTTPException(422, "Фразы исключений: от 3 до 120 символов")
    if body.kind == "keywords":
        phrases = sorted(set(x.strip() for x in body.phrases if x.strip()))
        if body.match_type != "flexible" and (not phrases or any(len(x) < 3 or len(x) > 120 for x in phrases)):
            raise HTTPException(422, "Введите ключевые фразы длиной от 3 до 120 символов")
        terms = []
        if body.match_type == "flexible":
            for item in body.terms:
                if not isinstance(item, dict) or set(item) - {"text", "weight", "required"}:
                    raise HTTPException(422, "Некорректные поля взвешенного термина")
                phrase = item.get("text")
                weight = item.get("weight", 1)
                required = item.get("required", False)
                if not isinstance(phrase, str) or not 2 <= len(phrase.strip()) <= 120:
                    raise HTTPException(422, "Длина термина: 2–120 символов")
                if type(weight) is not int or not 1 <= weight <= 100 or type(required) is not bool:
                    raise HTTPException(422, "Вес: 1–100; required должен быть логическим")
                terms.append({"text": phrase.strip(), "weight": weight, "required": required})
            if not terms:
                raise HTTPException(422, "Добавьте хотя бы один взвешенный термин")
        return {"phrases": phrases, "match_type": body.match_type,
                "terms": terms, "min_score": body.min_score, "window": body.window,
                "ordered": body.ordered, "exclude_phrases": excludes}
    if body.kind == "regex":
        try:
            safe_regex(body.pattern)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"pattern": body.pattern, "exclude_phrases": excludes}
    if body.kind == "reference":
        ids = set(body.reference_ids)
        if not ids or len(ids) != len(body.reference_ids):
            raise HTTPException(422, "Выберите уникальные эталонные документы")
        existing = set(session.scalars(select(Reference.id).where(Reference.id.in_(ids))))
        if ids != existing:
            raise HTTPException(422, "Один или несколько эталонов не существуют")
        return {
            "reference_ids": sorted(ids),
            "min_similarity": body.min_similarity,
            "exclude_phrases": excludes,
        }
    if body.kind == "ml":
        return {"min_confidence": body.min_confidence, "exclude_phrases": excludes}
    raise HTTPException(422, "Неизвестный тип правила")


def validate(body, session, *, existing_id=None):
    name = body.name.strip()
    group = body.group_name.strip()
    if not name or not group:
        raise HTTPException(422, "Введите название и группу")
    duplicate = session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower()))
    if duplicate and duplicate != existing_id:
        raise HTTPException(409, "Категория с таким названием уже существует")
    rules = [(rule, rule_config(rule, session)) for rule in body.rules]
    if len(rules) == 0:
        raise HTTPException(422, "Добавьте хотя бы одно правило обнаружения")
    return name, group, rules


@router.post("")
def create(body: CategoryBody, account=Depends(admin), session=Depends(db)):
    name, group, rules = validate(body, session)
    row = Category(
        id="custom-" + uuid.uuid4().hex,
        name=name,
        group_name=group,
        description=body.description.strip(),
        mode="custom",
        active=body.active,
        match_mode=body.match_mode,
        keywords=[],
        reference_id=None,
    )
    session.add(row)
    session.flush()
    for item, config in rules:
        session.add(
            CategoryRule(
                category_id=row.id,
                kind=item.kind,
                title=item.title.strip(),
                enabled=item.enabled,
                risk=item.risk,
                priority=item.priority,
                config=config,
            )
        )
    session.add(
        Audit(
            actor=account.id,
            action="category_create",
            target=row.id,
            details={"name": row.name, "rules": len(rules)},
        )
    )
    session.commit()
    return present(row, list(session.scalars(select(CategoryRule).where(CategoryRule.category_id == row.id))))


@router.put("/{category_id}")
def update(category_id: str, body: CategoryBody, account=Depends(admin), session=Depends(db)):
    row = session.get(Category, category_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    if row.mode in {"builtin", "label"}:
        raise HTTPException(409, "Системные категории нельзя изменять")
    name, group, rules = validate(body, session, existing_id=category_id)
    before = {
        "name": row.name,
        "match_mode": row.match_mode,
        "rule_ids": list(
            session.scalars(select(CategoryRule.id).where(CategoryRule.category_id == category_id))
        ),
    }
    row.name, row.group_name, row.description = name, group, body.description.strip()
    row.active, row.match_mode, row.mode = body.active, body.match_mode, "custom"
    # Rule replacement is atomic; historical incident findings remain immutable.
    session.execute(delete(CategoryRule).where(CategoryRule.category_id == category_id))
    session.flush()
    for item, config in rules:
        session.add(
            CategoryRule(
                category_id=row.id,
                kind=item.kind,
                title=item.title.strip(),
                enabled=item.enabled,
                risk=item.risk,
                priority=item.priority,
                config=config,
            )
        )
    session.add(
        Audit(
            actor=account.id,
            action="category_update",
            target=row.id,
            details={"before": before, "name": name, "rule_count": len(rules)},
        )
    )
    session.commit()
    return present(row, list(session.scalars(select(CategoryRule).where(CategoryRule.category_id == row.id))))


@router.post("/{category_id}/archive")
def archive(category_id: str, account=Depends(admin), session=Depends(db)):
    row = session.get(Category, category_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    if row.mode in {"builtin", "label"}:
        raise HTTPException(409, "Системные категории нельзя архивировать")
    row.active = False
    session.add(Audit(actor=account.id, action="category_archive", target=row.id))
    session.commit()
    return present(row, list(session.scalars(select(CategoryRule).where(CategoryRule.category_id == row.id))))
