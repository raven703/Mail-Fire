from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import admin, db
from app.models import Audit, Message, Setting
from app.retention import DEFAULTS, cleanup

router = APIRouter(prefix="/api/retention", tags=["Retention"])


class RetentionBody(BaseModel):
    ordinary_days: int = Field(default=30, ge=1, le=36500)
    unconfirmed_days: int = Field(default=365, ge=1, le=36500)
    confirmed_days: int = Field(default=365, ge=1, le=36500)
    audit_days: int = Field(default=365, ge=1, le=36500)
    logs_days: int = Field(default=30, ge=1, le=36500)
    metrics_days: int = Field(default=30, ge=1, le=36500)
    paused: bool = False


@router.get("")
def config(account=Depends(admin), session=Depends(db)):
    row = session.get(Setting, "retention")
    return DEFAULTS | (row.value if row else {})


@router.put("")
def save(body: RetentionBody, account=Depends(admin), session=Depends(db)):
    row = session.get(Setting, "retention")
    if not row:
        row = Setting(key="retention", value={})
        session.add(row)
    row.value = body.model_dump()
    session.add(Audit(actor=account.id, action="retention_config", target="retention", details=row.value))
    session.commit()
    return row.value


class CleanupBody(BaseModel):
    dry_run: bool = True
    confirm: str = ""


@router.post("/cleanup")
def run(body: CleanupBody, account=Depends(admin)):
    if not body.dry_run and body.confirm != "DELETE_EXPIRED":
        raise HTTPException(422, "Требуется явное подтверждение DELETE_EXPIRED")
    return cleanup(body.dry_run)


class HoldBody(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=1000)


@router.put("/messages/{message_id}/hold")
def hold(message_id: str, body: HoldBody, account=Depends(admin), session=Depends(db)):
    message = session.get(Message, message_id, with_for_update=True)
    if not message:
        raise HTTPException(404)
    message.legal_hold = body.enabled
    session.add(Audit(actor=account.id, action="legal_hold", target=message_id, details=body.model_dump()))
    session.commit()
    return {"legal_hold": message.legal_hold}
