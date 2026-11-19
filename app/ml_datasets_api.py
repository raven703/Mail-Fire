"""Import externally labeled datasets; explicit per-example approval is mandatory."""

import hashlib
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api import admin, analyst, db
from app.categories import available_categories
from app.datasets import parse_dataset
from app.ml import group_hash
from app.models import Audit, Category, MLDataset, TrainingExample

router = APIRouter(prefix="/api/ml/datasets", tags=["ML datasets"])
MAX_IMPORT_BYTES = 12 * 1024 * 1024


def permitted(account):
    if not account.originals:
        raise HTTPException(403, "Для работы с обучающими текстами требуется доступ к оригиналам")


def preview(dataset):
    return {
        "id": dataset.id, "name": dataset.name, "source": dataset.source,
        "description": dataset.description, "version": dataset.version,
        "status": dataset.status, "fingerprint": dataset.fingerprint,
        "example_count": dataset.example_count, "created_at": dataset.created_at,
    }


@router.get("")
def datasets(account=Depends(analyst), session=Depends(db)):
    permitted(account)
    return {"items": [preview(x) for x in session.scalars(
        select(MLDataset).order_by(MLDataset.created_at.desc()).limit(100)
    )]}


@router.post("/import", status_code=201)
async def import_dataset(
    file: UploadFile = File(...),
    name: str = Form(..., min_length=2, max_length=160),
    source: str = Form("external-llm", max_length=120),
    description: str = Form("", max_length=2000),
    label_mapping: str = Form("{}"),
    account=Depends(admin),
    session=Depends(db),
):
    permitted(account)
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "Файл датасета превышает 12 МиБ")
    try:
        requested = json.loads(label_mapping)
        if not isinstance(requested, dict) or len(requested) > 100:
            raise ValueError("Некорректное сопоставление категорий")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in requested.items()):
            raise ValueError("Сопоставление категорий должно содержать строки")
        rows = list(session.scalars(select(Category).where(Category.active.is_(True))))
        valid = {c.id: c.id for c in rows}
        valid.update({c.name: c.id for c in rows})
        valid.update(requested)
        if not available_categories(session, list(valid.values())):
            raise ValueError("В сопоставлении есть неизвестные или архивированные категории")
        examples = parse_dataset(raw, file.filename or "", valid)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    fingerprint = hashlib.sha256(raw).hexdigest()
    session.execute(__import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(hashtext('ml-dataset-import'))"))
    existing = session.scalar(select(MLDataset).where(MLDataset.fingerprint == fingerprint))
    if existing:
        raise HTTPException(409, f"Этот файл уже загружен как датасет {existing.id}")
    version = (session.scalar(select(func.max(MLDataset.version)).where(MLDataset.name == name.strip())) or 0) + 1
    dataset = MLDataset(
        name=name.strip(), source=source.strip(), description=description.strip(),
        version=version, status="REVIEW", fingerprint=fingerprint, example_count=len(examples),
    )
    session.add(dataset)
    session.flush()
    for example in examples:
        session.add(TrainingExample(
            text=example["text"], labels=example["labels"], approved=False,
            group_sha=group_hash(example["text"]), dataset_id=dataset.id,
            source="external-llm" if source.strip() == "external-llm" else "import",
        ))
    session.add(Audit(
        actor=account.id, action="ml_dataset_import", target=dataset.id,
        details={"rows":len(examples), "sha256":fingerprint, "source":source.strip()},
    ))
    session.commit()
    return preview(dataset)


@router.get("/{dataset_id}/examples")
def examples(
    dataset_id: str, offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    approved: bool | None = None,
    account=Depends(analyst), session=Depends(db),
):
    permitted(account)
    dataset = session.get(MLDataset, dataset_id)
    if not dataset:
        raise HTTPException(404)
    query = select(TrainingExample).where(TrainingExample.dataset_id == dataset_id)
    if approved is not None:
        query = query.where(TrainingExample.approved.is_(approved))
    result = list(session.scalars(query.order_by(TrainingExample.created_at, TrainingExample.id).offset(offset).limit(limit)))
    return {"items": [
        {"id":x.id,"text":x.text,"labels":x.labels,"approved":x.approved,"reviewed_by":x.reviewed_by}
        for x in result
    ], "offset":offset, "limit":limit}


class Review(BaseModel):
    labels: list[str] = Field(default_factory=list, max_length=20)
    approved: bool


@router.put("/{dataset_id}/examples/{example_id}")
def review_example(
    dataset_id: str, example_id: str, body: Review,
    account=Depends(analyst), session=Depends(db),
):
    permitted(account)
    row = session.scalar(select(TrainingExample).where(
        TrainingExample.id == example_id, TrainingExample.dataset_id == dataset_id
    ).with_for_update())
    if not row:
        raise HTTPException(404)
    labels = sorted(set(body.labels)) or ["NORMAL"]
    if "NORMAL" in labels and len(labels) > 1:
        raise HTTPException(422, "NORMAL не сочетается с другими метками")
    if not available_categories(session, labels):
        raise HTTPException(422, "Неизвестная или архивированная категория")
    before = {"labels": list(row.labels), "approved": row.approved}
    row.labels = labels
    row.approved = body.approved
    row.reviewed_by = account.id
    session.add(Audit(actor=account.id, action="ml_dataset_review",
                      target=row.id, details={"dataset_id":dataset_id,"before":before,"labels":labels,"approved":body.approved}))
    session.commit()
    return {"id":row.id,"labels":row.labels,"approved":row.approved}


@router.get("/{dataset_id}/stats")
def stats(dataset_id: str, account=Depends(analyst), session=Depends(db)):
    permitted(account)
    dataset = session.get(MLDataset, dataset_id)
    if not dataset:
        raise HTTPException(404)
    values = list(session.execute(
        select(TrainingExample.labels, TrainingExample.approved).where(TrainingExample.dataset_id == dataset_id)
    ))
    labels = {}
    for group, approved in values:
        for category in group:
            info = labels.setdefault(category, {"total":0,"approved":0})
            info["total"] += 1
            info["approved"] += int(approved)
    return {"dataset": preview(dataset), "total":len(values),
            "approved":sum(bool(x[1]) for x in values), "labels":labels}
