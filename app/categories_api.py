"""Public catalog read; audited administrator-only category lifecycle."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api import admin, db, user
from app.models import Audit, Category, Reference

router = APIRouter(prefix="/api/categories", tags=["Categories"])


class CategoryBody(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    group_name: str = Field(default="Другое", min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    mode: Literal["ml", "keywords", "reference"] = "ml"
    keywords: list[str] = Field(default_factory=list, max_length=30)
    reference_id: str | None = None
    active: bool = True


def present(row):
    return {
        "id": row.id,
        "name": row.name,
        "group_name": row.group_name,
        "description": row.description,
        "mode": row.mode,
        "keywords": row.keywords,
        "reference_id": row.reference_id,
        "active": row.active,
        "system": row.mode in {"builtin", "label"},
    }


@router.get("")
def listing(account=Depends(user), session=Depends(db)):
    rows = session.scalars(select(Category).order_by(Category.group_name, Category.name))
    return {"items": [present(row) for row in rows]}


def validate(body, session, *, existing_id=None):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Введите название категории")
    duplicate = session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower()))
    if duplicate and duplicate != existing_id:
        raise HTTPException(409, "Категория с таким именем существует")
    keywords = sorted({word.strip() for word in body.keywords if word.strip()})
    if any(len(word) < 3 or len(word) > 120 for word in keywords):
        raise HTTPException(422, "Ключевые фразы: от 3 до 120 символов")
    if body.mode == "keywords" and not keywords:
        raise HTTPException(422, "Для поиска по фразам нужно хотя бы одно ключевое слово")
    if body.mode == "reference":
        if not body.reference_id or not session.get(Reference, body.reference_id):
            raise HTTPException(422, "Выберите существующий эталонный документ")
    elif body.reference_id:
        raise HTTPException(422, "Эталон допустим только для режима «По эталону»")
    return name, keywords


@router.post("")
def create(body: CategoryBody, account=Depends(admin), session=Depends(db)):
    name, keywords = validate(body, session)
    row = Category(
        id="custom-" + uuid.uuid4().hex,
        name=name,
        group_name=body.group_name.strip(),
        description=body.description.strip(),
        mode=body.mode,
        keywords=keywords,
        reference_id=body.reference_id,
        active=body.active,
    )
    session.add(row)
    session.add(Audit(actor=account.id, action="category_create", target=row.id, details={"name": row.name, "mode": row.mode}))
    session.commit()
    return present(row)


@router.put("/{category_id}")
def update(category_id: str, body: CategoryBody, account=Depends(admin), session=Depends(db)):
    row = session.get(Category, category_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    if row.mode in {"builtin", "label"}:
        raise HTTPException(409, "Системную категорию нельзя изменять")
    name, keywords = validate(body, session, existing_id=row.id)
    row.name, row.group_name, row.description = name, body.group_name.strip(), body.description.strip()
    row.mode, row.keywords, row.reference_id, row.active = body.mode, keywords, body.reference_id, body.active
    session.add(Audit(actor=account.id, action="category_update", target=row.id,
                      details={"name": row.name, "mode": row.mode, "active": row.active}))
    session.commit()
    return present(row)


@router.post("/{category_id}/archive")
def archive(category_id: str, account=Depends(admin), session=Depends(db)):
    row = session.get(Category, category_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    if row.mode in {"builtin", "label"}:
        raise HTTPException(409, "Системную категорию нельзя архивировать")
    row.active = False
    session.add(Audit(actor=account.id, action="category_archive", target=row.id))
    session.commit()
    return present(row)
