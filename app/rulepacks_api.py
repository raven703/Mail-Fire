"""Administrator-only rulepack transfer; preview is read-only, apply revalidates."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.api import admin, db
from app.models import Audit
from app.rulepacks import Rulepack, apply_pack, export_pack, inspect_pack

router = APIRouter(prefix="/api/rulepacks", tags=["rulepacks"])


async def incoming(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, "Набор правил не может превышать 1 МиБ")
    try:
        data = json.loads(raw)
        pack = Rulepack.model_validate(data["pack"])
        update = data.get("update_existing", False)
        if not isinstance(update, bool):
            raise ValueError("update_existing должен быть boolean")
        return pack, update
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/export")
def export(account=Depends(admin), session=Depends(db)):
    pack = export_pack(session)
    session.add(Audit(actor=account.id, action="rulepack_export", target=pack.name))
    session.commit()
    return pack.model_dump()


@router.post("/preview")
async def preview(request: Request, account=Depends(admin), session=Depends(db)):
    pack, update = await incoming(request)
    try:
        plan = inspect_pack(session, pack, update_existing=update)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"changes": plan, "warning": "Импортированные политики будут выключены"}


@router.post("/apply")
async def apply(request: Request, account=Depends(admin), session=Depends(db)):
    pack, update = await incoming(request)
    try:
        changes = apply_pack(session, pack, actor=account.id, update_existing=update)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.add(Audit(actor=account.id, action="rulepack_apply", target=pack.name,
                      details={"sha256": hashlib.sha256(pack.model_dump_json().encode()).hexdigest(),
                               "update_existing": update, "changes": changes}))
    session.commit()
    return {"changes": changes}
