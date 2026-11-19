from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update

from app.api import admin, analyst, db, serialize, user
from app.categories import available_categories
from app.ml import group_hash, snapshot_hash
from app.models import Audit, Category, Content, Incident, Job, MailEvent, MLDataset, Message, MLModel, TrainingExample

router = APIRouter(prefix="/api/ml", tags=["ML"])


class ExampleBody(BaseModel):
    text: str = Field(min_length=10, max_length=100000)
    labels: list[str] = Field(min_length=1, max_length=20)
    approved: bool = False


@router.post("/examples")
def add_example(body: ExampleBody, account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403, "Нет разрешения на работу с содержимым")
    if not available_categories(session, body.labels):
        raise HTTPException(422, "Выберите активные категории из справочника")
    row = TrainingExample(
        text=body.text,
        labels=sorted(set(body.labels)),
        approved=body.approved,
        group_sha=group_hash(body.text),
        source="manual", reviewed_by=account.id if body.approved else None,
    )
    session.add(row)
    session.add(Audit(actor=account.id, action="ml_label", target=row.group_sha))
    session.commit()
    return serialize(row)


class IncidentExampleBody(BaseModel):
    labels: list[str] = Field(min_length=1, max_length=20)
    approved: bool = False


@router.post("/incidents/{incident_id}/example")
def from_incident(incident_id: str, body: IncidentExampleBody, account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403, "Нет доступа к содержимому письма")
    if not available_categories(session, body.labels):
        raise HTTPException(422, "Выберите действующие категории из справочника")
    incident = session.get(Incident, incident_id, with_for_update=True)
    if not incident:
        raise HTTPException(404)
    event = session.get(MailEvent, incident.event_id)
    message = session.get(Message, event.message_id)
    content = session.get(Content, message.content_id) if message.content_id else None
    if not content or len(content.text.strip()) < 10:
        raise HTTPException(409, "Содержимое письма ещё не извлечено")
    previous = session.scalar(
        select(TrainingExample).where(TrainingExample.source_incident_id == incident_id)
    )
    if previous:
        raise HTTPException(409, "Инцидент уже связан с обучающим примером")
    example = TrainingExample(
        text=content.text[:100000],
        labels=sorted(set(body.labels)),
        approved=body.approved,
        group_sha=group_hash(content.text[:100000]),
        source_incident_id=incident_id,
        source="incident", reviewed_by=account.id if body.approved else None,
    )
    session.add(example)
    session.add(
        Audit(
            actor=account.id,
            action="ml_label_from_incident",
            target=incident_id,
            details={"categories": example.labels, "approved": example.approved},
        )
    )
    session.commit()
    return serialize(example)


@router.get("/models")
def models(account=Depends(user), session=Depends(db)):
    rows = list(session.scalars(select(MLModel).order_by(MLModel.created_at.desc())))
    return {
        "status": "TRAINED" if any(r.active for r in rows) else "UNTRAINED",
        "items": [serialize(r) for r in rows],
    }


class TrainBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    min_f1: float = Field(default=0.7, ge=0.5, le=1)
    engine: str = Field(default="tfidf", pattern="^(tfidf|setfit|rubert)$")
    category_id: str | None = None
    dataset_id: str | None = None


@router.post("/train", status_code=202)
def training(body: TrainBody, account=Depends(admin), session=Depends(db)):
    if body.engine in {"setfit", "rubert"}:
        category = session.get(Category, body.category_id) if body.category_id else None
        if not category or not category.active or category.mode == "label":
            raise HTTPException(422, "Выберите активную категорию для нейросетевой модели")
    elif body.category_id:
        raise HTTPException(422, "TF-IDF обучается как общая многометочная модель")
    if body.dataset_id and not session.get(MLDataset, body.dataset_id):
        raise HTTPException(422, "Датасет не найден")
    query = select(TrainingExample).where(TrainingExample.approved.is_(True))
    if body.dataset_id:
        query = query.where(TrainingExample.dataset_id == body.dataset_id)
    rows = list(session.scalars(query.limit(10001)))
    if len(rows) > 10000:
        raise HTTPException(422, "Используйте выделенный training worker для более 10000 примеров")
    if len(rows) < 30:
        raise HTTPException(422, "Нужно не менее 30 различных утверждённых примеров")
    snapshot = snapshot_hash([{"text": r.text, "labels": r.labels} for r in rows])
    job = Job(kind="ml_train", payload={
        "name":body.name, "min_f1":body.min_f1, "engine":body.engine,
        "category_id":body.category_id, "dataset_id":body.dataset_id,
        "snapshot_sha":snapshot, "progress":0,
    })
    session.add(job)
    session.add(Audit(actor=account.id, action="ml_train", target=body.name))
    session.commit()
    return serialize(job)


@router.post("/models/{model_id}/publish")
def publish(model_id: str, account=Depends(admin), session=Depends(db)):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext('ml-publication'))"))
    model = session.get(MLModel, model_id)
    if not model:
        raise HTTPException(404)
    if not model.eligible:
        raise HTTPException(409, "Модель не прошла метрики качества")
    session.execute(update(MLModel).where(
        MLModel.category_id == model.category_id
        if model.category_id is not None
        else MLModel.category_id.is_(None)
    ).values(active=False))
    model.active = True
    session.add(Audit(actor=account.id, action="ml_publish_or_rollback", target=model.id))
    session.commit()
    return serialize(model)


class InferenceBody(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


@router.post("/infer")
def inference(body: InferenceBody, account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403, "Требуется доступ к оригиналам")
    from app.ml_runtime import infer_active

    predictions, errors = infer_active(session, body.text)
    return {
        "status": "PARTIAL" if errors else "ANALYZED" if predictions else "UNTRAINED",
        "predictions": predictions, "errors": errors,
    }
