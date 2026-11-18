"""Administrative accounts: no password hashes in API responses or audit."""

from typing import Literal

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text

from app.api import admin, db
from app.models import Account, Audit, LoginSession

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


class AccountBody(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[\w.@+-]+$")
    role: Literal["admin", "analyst", "observer"]
    originals: bool = False
    enabled: bool = True
    password: str | None = Field(default=None, min_length=12, max_length=128)


def public(row):
    return {k: getattr(row, k) for k in ("id", "username", "role", "originals", "enabled")}


@router.get("")
def listing(account=Depends(admin), session=Depends(db)):
    return {"items": [public(r) for r in session.scalars(select(Account).order_by(Account.username))]}


def save(body, account, session, account_id=None):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext('accounts-admin'))"))
    row = session.get(Account, account_id) if account_id else None
    if account_id and not row:
        raise HTTPException(404)
    duplicate = session.scalar(select(Account).where(Account.username == body.username))
    if duplicate and (not row or duplicate.id != row.id):
        raise HTTPException(409, "Имя уже используется")
    if row and row.id == account.id and (not body.enabled or body.role != "admin"):
        raise HTTPException(409, "Нельзя отключить собственный административный доступ")
    if row and row.enabled and row.role == "admin" and (not body.enabled or body.role != "admin"):
        others = session.scalar(
            select(Account.id)
            .where(Account.enabled.is_(True), Account.role == "admin", Account.id != row.id)
            .limit(1)
        )
        if not others:
            raise HTTPException(409, "Нельзя отключить последнего администратора")
    if not row:
        if not body.password:
            raise HTTPException(422, "Укажите пароль")
        row = Account(username=body.username, role=body.role, password_hash="")
        session.add(row)
    for key in ("username", "role", "enabled", "originals"):
        setattr(row, key, getattr(body, key))
    if body.password:
        row.password_hash = PasswordHasher().hash(body.password)
    session.flush()
    session.execute(delete(LoginSession).where(LoginSession.account_id == row.id))
    session.add(Audit(actor=account.id, action="account_update", target=row.id, details=public(row)))
    session.commit()
    return public(row)


@router.post("")
def create(body: AccountBody, account=Depends(admin), session=Depends(db)):
    return save(body, account, session)


@router.put("/{account_id}")
def update(account_id: str, body: AccountBody, account=Depends(admin), session=Depends(db)):
    return save(body, account, session, account_id)
