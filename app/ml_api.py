from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update

from app.api import admin, analyst, db, serialize, user
from app.ml import group_hash, infer
from app.models import Audit, Job, MLModel, TrainingExample

router = APIRouter(prefix="/api/ml", tags=["ML"])


class ExampleBody(BaseModel):
    text: str = Field(min_length=10, max_length=100000)
    labels: list[str] = Field(min_length=1, max_length=20)
    approved: bool = False


@router.post("/examples")
def add_example(body: ExampleBody, account=Depends(analyst), session=Depends(db)):
    if any(not label.strip() or len(label) > 100 for label in body.labels):
        raise HTTPException(422, "Некорректная категория")
    row = TrainingExample(
        text=body.text,
        labels=sorted(set(body.labels)),
        approved=body.approved,
        group_sha=group_hash(body.text),
    )
    session.add(row)
    session.add(Audit(actor=account.id, action="ml_label", target=row.group_sha))
    session.commit()
    return serialize(row)


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


@router.post("/train", status_code=202)
def training(body: TrainBody, account=Depends(admin), session=Depends(db)):
    rows = list(
        session.scalars(select(TrainingExample).where(TrainingExample.approved.is_(True)).limit(10001))
    )
    if len(rows) > 10000:
        raise HTTPException(422, "Используйте выделенный training worker для более 10000 примеров")
    if len(rows) < 30:
        raise HTTPException(422, "Нужно не менее 30 различных утверждённых примеров")
    job = Job(kind="ml_train", payload={"name": body.name, "min_f1": body.min_f1, "progress": 0})
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
    session.execute(update(MLModel).values(active=False))
    model.active = True
    session.add(Audit(actor=account.id, action="ml_publish_or_rollback", target=model.id))
    session.commit()
    return serialize(model)


class InferenceBody(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


@router.post("/infer")
def inference(body: InferenceBody, account=Depends(analyst), session=Depends(db)):
    model = session.scalar(select(MLModel).where(MLModel.active.is_(True)))
    if not model:
        return {"status": "UNTRAINED", "predictions": []}
    return {"status": "ANALYZED", "model_id": model.id, "predictions": infer(model.artifact, body.text)}
