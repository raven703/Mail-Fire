from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select

from app.api import analyst, db, serialize, user
from app.config import settings
from app.fingerprints import fingerprint
from app.mail import put_blob
from app.models import Audit, Reference
from app.sandbox import call

router = APIRouter(prefix="/api/references", tags=["Reference documents"])


@router.get("")
def references(account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    return {
        "items": [
            serialize(r)
            for r in session.scalars(select(Reference).order_by(Reference.created_at.desc()).limit(200))
        ]
    }


@router.post("")
async def upload_reference(file: UploadFile, account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    data = await file.read(settings().max_message_bytes + 1)
    if len(data) > settings().max_message_bytes:
        raise HTTPException(413)
    result = call("extract", data, file.filename or "document.txt")
    if not result["text"].strip():
        raise HTTPException(422, "Текст не извлечён; документ не проиндексирован")
    row = Reference(
        name=file.filename or "document",
        blob_sha=put_blob(session, data),
        text=result["text"],
        fingerprint=fingerprint(result["text"]),
    )
    session.add(row)
    session.add(Audit(actor=account.id, action="reference_upload", target=row.name))
    session.commit()
    return serialize(row)
