from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy import select

from app.api import analyst, db, serialize, user
from app.config import settings
from app.fingerprints import fingerprint
from app.document_templates import TEMPLATES, match_document, template_config
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
async def upload_reference(file: UploadFile, template_type: str = Form(""), account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    data = await file.read(settings().max_message_bytes + 1)
    if len(data) > settings().max_message_bytes:
        raise HTTPException(413)
    result = call("extract", data, file.filename or "document.txt")
    if not result["text"].strip():
        raise HTTPException(422, "Текст не извлечён; документ не проиндексирован")
    if template_type:
        if template_type not in TEMPLATES:
            raise HTTPException(422, "Неизвестный тип документа")
        spec = template_config(template_type)
        sample = match_document(result["text"], spec)
        if not sample:
            raise HTTPException(422, "Образец не подтверждает тип документа: недостаточно постоянных полей или номер не прошёл проверку")
        # Do not retain image or variable OCR fields from a sample.
        safe_text = " ".join(spec["anchors"])
        row = Reference(
            name=file.filename or TEMPLATES[template_type]["label"],
            blob_sha=put_blob(session, ("document-template:" + template_type).encode()),
            text=safe_text,
            fingerprint={"document_template": spec},
        )
    else:
        row = Reference(
            name=file.filename or "document",
            blob_sha=put_blob(session, data),
            text=result["text"],
            fingerprint=fingerprint(result["text"]),
        )
    session.add(row)
    session.add(Audit(actor=account.id, action="reference_upload", target=row.name))
    session.commit()
    from app.semantic import index_document

    if not template_type:
        index_document(session, "reference", row.id, row.text)
        session.commit()
    return serialize(row)
