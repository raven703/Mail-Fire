from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.api import admin, db, user
from app.models import Audit, Content, Reference
from app.semantic import MODEL, index_document, search

router = APIRouter(prefix="/api/semantic", tags=["Semantic search"])


class Query(BaseModel):
    query: str = Field(min_length=3, max_length=10000)
    source_type: str | None = None


@router.post("/search")
def searching(body: Query, account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    if body.source_type not in {None, "content", "reference"}:
        raise HTTPException(422)
    result = search(session, body.query, body.source_type)
    session.add(Audit(actor=account.id, action="semantic_search", target="semantic_chunks"))
    session.commit()
    return {"model": MODEL, "items": result, "warning": "Сходство не является доказательством утечки"}


@router.post("/reindex")
def reindex(account=Depends(admin), session=Depends(db)):
    count = 0
    for kind, model in [("reference", Reference), ("content", Content)]:
        for row in session.scalars(select(model).limit(1000)):
            count += index_document(session, kind, row.id, row.text)
    session.add(Audit(actor=account.id, action="semantic_reindex", target=MODEL))
    session.commit()
    return {"chunks_indexed": count, "model": MODEL, "document_limit_per_type": 1000}


@router.get("/status")
def status(account=Depends(user), session=Depends(db)):
    rows = session.execute(
        text("SELECT source_type,model,count(*) AS chunks FROM semantic_chunks GROUP BY source_type,model")
    )
    return {"items": [dict(r._mapping) for r in rows]}
