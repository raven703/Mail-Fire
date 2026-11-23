from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.api import admin, db, serialize, user
from app.models import Attachment, Audit, Blob, Outbox, Setting

router = APIRouter(prefix="/api", tags=["Administration"])


class Destination(BaseModel):
    url: str = Field(max_length=2048)
    enabled: bool = True


class IntegrationBody(BaseModel):
    destinations: list[Destination] = Field(max_length=20)


@router.get("/integrations")
def integrations(account=Depends(admin), session=Depends(db)):
    row = session.get(Setting, "integrations")
    return row.value if row else {"destinations": []}


@router.put("/integrations")
def save_integrations(body: IntegrationBody, account=Depends(admin), session=Depends(db)):
    for destination in body.destinations:
        parsed = urlsplit(destination.url)
        if (
            parsed.scheme not in {"http", "https", "syslog", "cef"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise HTTPException(422, "Некорректный адрес SIEM/Webhook")
    row = session.get(Setting, "integrations")
    if not row:
        row = Setting(key="integrations", value={})
        session.add(row)
    row.value = body.model_dump()
    session.add(Audit(actor=account.id, action="integration_config", target="integrations"))
    session.commit()
    return row.value


@router.get("/outbox")
def outbox(offset: int = 0, account=Depends(admin), session=Depends(db)):
    rows = session.scalars(select(Outbox).order_by(Outbox.created_at.desc()).offset(max(0, offset)).limit(50))
    return {"items": [serialize(r) for r in rows]}


@router.get("/search")
def search(q: str, offset: int = 0, account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    if not q.strip() or len(q) > 500:
        raise HTTPException(422)
    rows = session.execute(
        text("""SELECT m.id, m.subject, m.sender, m.status,
        ts_rank(to_tsvector('simple', c.text), plainto_tsquery('simple', :q)) AS rank
        FROM messages m JOIN contents c ON c.id=m.content_id
        WHERE to_tsvector('simple', c.text) @@ plainto_tsquery('simple', :q)
        ORDER BY rank DESC LIMIT 50 OFFSET :offset"""),
        {"q": q, "offset": max(0, offset)},
    )
    session.add(Audit(actor=account.id, action="fulltext_search", target="messages"))
    session.commit()
    return {"items": [dict(row._mapping) for row in rows]}


@router.get("/messages/{message_id}/attachments")
def attachments(message_id: str, account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    return {
        "items": [
            serialize(r)
            for r in session.scalars(select(Attachment).where(Attachment.message_id == message_id))
        ]
    }


@router.get("/attachments/{attachment_id}/original")
def attachment_original(attachment_id: str, account=Depends(user), session=Depends(db)):
    from fastapi import Response

    if not account.originals:
        raise HTTPException(403)
    row = session.get(Attachment, attachment_id)
    if not row:
        raise HTTPException(404)
    data = session.get(Blob, row.blob_sha).data
    session.add(Audit(actor=account.id, action="attachment_download", target=row.id))
    session.commit()
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="attachment.bin"',
            "X-Content-Type-Options": "nosniff",
        },
    )


PREVIEW_MIME = {
    "application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp",
}


@router.get("/attachments/{attachment_id}/preview")
def attachment_preview(attachment_id: str, account=Depends(user), session=Depends(db)):
    """Display only allowlisted passive formats. Others use extracted plain text."""
    from fastapi import Response

    if not account.originals:
        raise HTTPException(403, "Нет доступа к содержимому")
    row = session.get(Attachment, attachment_id)
    if not row:
        raise HTTPException(404)
    if row.mime.lower().split(";")[0].strip() not in PREVIEW_MIME:
        raise HTTPException(415, "Предпросмотр файла недоступен, используйте извлечённый текст")
    blob = session.get(Blob, row.blob_sha)
    if not blob or len(blob.data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Вложение слишком большое для просмотра")
    mime = row.mime.lower().split(";")[0].strip()
    # Don't trust a MIME type supplied by an email: verify file signature.
    signatures = {
        "application/pdf": blob.data.startswith(b"%PDF-"),
        "image/png": blob.data.startswith(b"\\x89PNG\\r\\n\\x1a\\n"),
        "image/jpeg": blob.data.startswith(b"\\xff\\xd8\\xff"),
        "image/gif": blob.data.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": blob.data.startswith(b"RIFF") and blob.data[8:12] == b"WEBP",
    }
    if not signatures[mime]:
        raise HTTPException(415, "Неверный формат вложения")
    session.add(Audit(actor=account.id, action="attachment_preview", target=row.id))
    session.commit()
    return Response(blob.data, media_type=mime, headers={
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
        "Cache-Control": "no-store",
    })
