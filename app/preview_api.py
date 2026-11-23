"""Authorized passive document viewer, reusing stored extraction and DLP results."""

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import db, user
from app.models import Attachment, Audit, Blob, Content, Message
from app.sandbox import call

router = APIRouter(prefix="/api/attachments", tags=["Preview"])
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


def load(attachment_id, account, session):
    if not account.originals:
        raise HTTPException(403, "Нет доступа к содержимому")
    row = session.get(Attachment, attachment_id)
    if not row:
        raise HTTPException(404)
    return row


def findings_for(row, session):
    message = session.get(Message, row.message_id)
    content = session.get(Content, message.content_id) if message and message.content_id else None
    findings = (content.analysis or {}).get("findings", []) if content else []
    return [f for f in findings if f.get("attachment") == row.name or
            (f.get("excerpt") and f["excerpt"] in (row.text or ""))]


@router.get("/{attachment_id}/viewer")
def metadata(attachment_id: str, account=Depends(user), session=Depends(db)):
    row = load(attachment_id, account, session)
    blob = session.get(Blob, row.blob_sha)
    session.add(Audit(actor=account.id, action="attachment_preview", target=row.id))
    session.commit()
    mail = None
    if Path(row.name).suffix.lower() in {".eml", ".msg"} and blob and blob.size <= 20 * 1024**2:
        try:
            parsed = call("mail", blob.data)
            mail = {k: parsed.get(k) for k in ("subject", "sender", "recipients", "text")}
        except Exception:
            pass
    return {"text": row.text, "mail": mail, "status": row.status, "details": row.details,
            "size": blob.size if blob else 0, "findings": findings_for(row, session)}


@router.get("/{attachment_id}/page")
def page(attachment_id: str, page: int = Query(1, ge=1, le=1000),
         scale: float = Query(1, ge=0.5, le=2), highlight: bool = False,
         account=Depends(user), session=Depends(db)):
    row = load(attachment_id, account, session)
    blob = session.get(Blob, row.blob_sha)
    if not blob:
        raise HTTPException(404)
    if blob.size > 20 * 1024**2:
        raise HTTPException(413, "Максимальный размер просмотра — 20 МБ")
    data = blob.data
    suffix = Path(row.name).suffix.lower()
    try:
        if suffix in OFFICE:
            url = os.environ.get("CONVERTER_URL")
            if not url:
                raise HTTPException(503, "Сервис Office-конвертации не настроен")
            with httpx.Client(timeout=75, trust_env=False) as client:
                with client.stream("POST", url + "/convert?ext=" + suffix[1:], content=data) as response:
                    response.raise_for_status()
                    converted = bytearray()
                    for chunk in response.iter_bytes():
                        converted.extend(chunk)
                        if len(converted) > 20 * 1024**2:
                            raise ValueError("Converted document too large")
                    data = bytes(converted)
        excerpts = [f.get("excerpt", "")[:100] for f in findings_for(row, session)][:5] if highlight else []
        result = call("preview", data, json.dumps({"page": page, "scale": scale,
                                                  "highlights": excerpts}, ensure_ascii=False))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Оригинал недоступен для безопасного просмотра; используйте сохранённый текст") from None
    session.add(Audit(actor=account.id, action="attachment_preview_page", target=row.id,
                      details={"page": page}))
    session.commit()
    return {"image": "data:image/png;base64," + result["image"], "pages": result["pages"]}