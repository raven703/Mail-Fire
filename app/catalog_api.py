"""Live management data for policy, detector, reference and ML workspaces."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.api import admin, analyst, db, serialize, user
from app.models import (
    Audit,
    Blob,
    Incident,
    Job,
    MailEvent,
    MLModel,
    Policy,
    Reference,
    Setting,
    TrainingExample,
    now,
)
from app.workspace_api import PolicyBody, persist_policy
from app.text_normalizer import DEFAULTS as NORMALIZER_DEFAULTS

router = APIRouter(prefix="/api/catalog", tags=["Management"])
DETECTORS = {
    "pii": (
        "Персональные данные",
        "Presidio: российские ПДн, контрольные суммы ИНН/СНИЛС",
        ["EMAIL", "PHONE", "INN", "RU_INN", "RU_SNILS", "RU_PASSPORT", "RU_PHONE"],
    ),
    "static_files": (
        "Статический анализ вложений",
        "YARA и oletools; без исполнения кода",
        ["YARA", "OFFICE_MACRO"],
    ),
    "antivirus": ("Антивирус", "ClamAV INSTREAM; требует включённого сервиса", ["MALWARE"]),
    "secrets": ("Секреты и ключи", "Статические сигнатуры", ["SECRET", "PRIVATE_KEY"]),
    "confidential": ("Коммерческая тайна", "Контекстные словари", ["CONFIDENTIAL"]),
    "code": ("Исходный код и команды", "Статические эвристики", ["CODE", "SUSPICIOUS_COMMAND"]),
    "prompt": ("Prompt injection", "Контекстные эвристики", ["PROMPT_INJECTION"]),
    "reference": ("Эталонные документы", "Fingerprint / MinHash", ["REFERENCE_DOCUMENT"]),
    "semantic": ("Семантическое сходство", "Multilingual MiniLM / pgvector", ["SEMANTIC_REFERENCE"]),
    "ml": ("ML-классификатор", "TF-IDF / Logistic Regression", []),
    "normalizer": ("Нормализация текста", "Восстановление обфускаций перед LLM (оригинал сохраняется)", []),
}


@router.get("/policies")
def policies(include_archived: bool = False, account=Depends(user), session=Depends(db)):
    day = now().replace(tzinfo=None) - timedelta(days=1)
    week = day - timedelta(days=6)
    counts = dict(session.execute(
        text("""SELECT hit->>'policy_id', count(*) FROM incidents i
                CROSS JOIN LATERAL jsonb_array_elements(i.policy_hits) AS hit
                WHERE i.created_at >= :week GROUP BY hit->>'policy_id'"""),
        {"week": week},
    ).all())
    rows = list(session.scalars(select(Policy).where(Policy.archived.is_(False) if not include_archived else True).order_by(Policy.priority, Policy.name)))
    return {
        "items": [{**serialize(r), "hits": counts.get(r.id, 0)} for r in rows],
        "active": sum(r.enabled and not r.shadow for r in rows),
        "shadow": sum(r.enabled and r.shadow for r in rows),
        "daily_hits": session.scalar(
            select(func.count()).select_from(Incident).where(Incident.created_at >= day)
        ),
    }


class Toggle(BaseModel):
    enabled: bool


@router.put("/policies/{policy_id}/enabled")
def toggle_policy(policy_id: str, body: Toggle, account=Depends(admin), session=Depends(db)):
    row = session.get(Policy, policy_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    data = {
        **row.conditions,
        "name": row.name,
        "enabled": body.enabled,
        "shadow": row.shadow,
        "priority": row.priority,
    }
    return persist_policy(PolicyBody(**data), session, account, row)


@router.get("/history")
def history(account=Depends(user), session=Depends(db)):
    return {
        "items": [
            serialize(r)
            for r in session.scalars(
                select(Audit)
                .where(Audit.action == "policy_save")
                .order_by(Audit.created_at.desc())
                .limit(100)
            )
        ]
    }


@router.post("/reevaluate")
def reevaluate(account=Depends(admin), session=Depends(db)):
    # Bounded work: queue actual existing events; workers retain idempotent evaluation.
    ids = list(session.scalars(select(MailEvent.id).order_by(MailEvent.created_at.desc()).limit(1000)))
    for event_id in ids:
        session.add(Job(kind="evaluate", payload={"event_id": event_id}))
    session.add(Audit(actor=account.id, action="policy_reevaluate", target="latest_1000_events"))
    session.commit()
    return {"queued": len(ids), "limit": 1000}


@router.get("/detectors")
def detectors(account=Depends(user), session=Depends(db)):
    row = session.get(Setting, "detectors")
    config = row.value if row else {}
    active_model = session.scalar(select(MLModel.id).where(MLModel.active.is_(True)))
    normalizer = session.get(Setting, "normalizer")
    norm_options = {**NORMALIZER_DEFAULTS,
                    **(normalizer.value if normalizer else {})}
    return {
        "items": [
            dict(
                id=key,
                name=value[0],
                engine=value[1],
                categories=value[2],
                enabled=norm_options["enabled"] if key == "normalizer" else config.get(key, True),
                available=key != "ml" or bool(active_model),
                **({"mode": norm_options["mode"], "sensitivity": norm_options["sensitivity"]}
                   if key == "normalizer" else {}),
            )
            for key, value in DETECTORS.items()
        ]
    }


@router.put("/detectors/{detector_id}")
def detector_settings(detector_id: str, body: Toggle, account=Depends(admin), session=Depends(db)):
    if detector_id not in DETECTORS:
        raise HTTPException(404)
    if detector_id == "normalizer":
        row = session.get(Setting, "normalizer", with_for_update=True)
        from app.text_normalizer import DEFAULTS
        if not row:
            row = Setting(key="normalizer", value=dict(DEFAULTS))
            session.add(row)
        row.value = {**DEFAULTS, **row.value, "enabled": body.enabled}
        session.add(Audit(actor=account.id, action="normalizer_config", target="normalizer", details=row.value))
        session.commit()
        return {"saved": True}
    row = session.get(Setting, "detectors", with_for_update=True)
    if not row:
        row = Setting(key="detectors", value={})
        session.add(row)
    row.value = {**row.value, detector_id: body.enabled}
    session.add(
        Audit(actor=account.id, action="detector_config", target=detector_id, details=body.model_dump())
    )
    session.commit()
    return {"saved": True}


@router.get("/references")
def references(
    q: str = Query("", max_length=200),
    offset: int = Query(0, ge=0),
    account=Depends(user),
    session=Depends(db),
):
    if not account.originals:
        raise HTTPException(403)
    query = select(Reference, Blob.size).join(Blob, Blob.sha == Reference.blob_sha)
    if q:
        query = query.where(Reference.name.ilike("%" + q + "%"))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    chunks = dict(
        session.execute(
            text(
                "SELECT source_id,count(*) FROM semantic_chunks WHERE source_type='reference' GROUP BY source_id"
            )
        ).all()
    )
    items = [
        {
            "id": r.id,
            "name": r.name,
            "created_at": r.created_at,
            "size": size,
            "chunks": chunks.get(r.id, 0),
            "status": "TEMPLATE" if "document_template" in (r.fingerprint or {}) else "INDEXED" if chunks.get(r.id) else "TEXT_EXTRACTED",
            "template_type": (r.fingerprint or {}).get("document_template", {}).get("kind"),
            "template_anchors": (r.fingerprint or {}).get("document_template", {}).get("anchors", []),
        }
        for r, size in session.execute(query.order_by(Reference.created_at.desc()).offset(offset).limit(50))
    ]
    return {
        "items": items,
        "total": total,
        "indexed": sum(bool(chunks.get(r)) for r in session.scalars(select(Reference.id))),
        "bytes": session.scalar(
            select(func.coalesce(func.sum(Blob.size), 0)).join(Reference, Reference.blob_sha == Blob.sha)
        ),
    }


@router.get("/references/{reference_id}")
def reference_detail(reference_id: str, account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    row = session.get(Reference, reference_id)
    if not row:
        raise HTTPException(404)
    matches = session.execute(
        text("""SELECT i.id, m.id AS message_id,m.subject,i.created_at,f.value->>'excerpt' AS excerpt,
        f.value->>'confidence' AS confidence FROM incidents i JOIN mail_events e ON e.id=i.event_id
        JOIN messages m ON m.id=e.message_id CROSS JOIN LATERAL jsonb_array_elements(i.findings) f(value)
        WHERE f.value->>'rule_id'=:id ORDER BY i.created_at DESC LIMIT 100"""),
        {"id": reference_id},
    )
    session.add(Audit(actor=account.id, action="reference_view", target=reference_id))
    result = {
        "id": row.id,
        "name": row.name,
        "text": row.text,
        "matches": [dict(r._mapping) for r in matches],
    }
    session.commit()
    return result


@router.post("/references/{reference_id}/reindex")
def reindex_reference(reference_id: str, account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    row = session.get(Reference, reference_id)
    if not row:
        raise HTTPException(404)
    if "document_template" in (row.fingerprint or {}):
        raise HTTPException(409, "Для шаблона типа документа семантический индекс не используется")
    job = Job(
        kind="semantic_reindex", payload={"items": [["reference", row.id]], "completed": 0, "progress": 0}
    )
    session.add(job)
    session.add(Audit(actor=account.id, action="reference_reindex", target=row.id))
    session.commit()
    return {"job_id": job.id, "queued": True}


@router.delete("/references/{reference_id}")
def delete_reference(reference_id: str, account=Depends(admin), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    row = session.get(Reference, reference_id)
    if not row:
        raise HTTPException(404)
    session.execute(
        text("DELETE FROM semantic_chunks WHERE source_type='reference' AND source_id=:id"), {"id": row.id}
    )
    session.add(Audit(actor=account.id, action="reference_delete", target=row.id))
    session.delete(row)
    session.commit()
    return {"deleted": True}


@router.get("/examples")
def examples(offset: int = Query(0, ge=0), account=Depends(analyst), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    return {
        "items": [
            serialize(r)
            for r in session.scalars(
                select(TrainingExample).order_by(TrainingExample.created_at.desc()).offset(offset).limit(50)
            )
        ],
        "total": session.scalar(select(func.count()).select_from(TrainingExample)),
        "approved": session.scalar(
            select(func.count()).select_from(TrainingExample).where(TrainingExample.approved.is_(True))
        ),
    }


@router.delete("/examples/{example_id}")
def delete_training_example(example_id: str, account=Depends(admin), session=Depends(db)):
    """Remove one training sample; preserve the audit trail without its text."""
    row = session.get(TrainingExample, example_id)
    if not row:
        raise HTTPException(404)
    if row.dataset_id:
        from app.models import MLDataset
        dataset = session.get(MLDataset, row.dataset_id, with_for_update=True)
        if dataset:
            dataset.example_count = max(0, dataset.example_count - 1)
            dataset.status = "REVIEW"
    session.add(Audit(actor=account.id, action="ml_example_delete", target=row.id,
                      details={"dataset_id": row.dataset_id, "source": row.source}))
    session.delete(row)
    session.commit()
    return {"deleted": True}

class NormalizerOptions(BaseModel):
    enabled: bool
    mode: Literal["detect", "augment"] = "detect"
    sensitivity: Literal["low", "medium", "high"] = "medium"


@router.put("/normalizer")
def update_normalizer(body: NormalizerOptions, account=Depends(admin), session=Depends(db)):
    row = session.get(Setting, "normalizer", with_for_update=True)
    if not row:
        row = Setting(key="normalizer", value={})
        session.add(row)
    row.value = body.model_dump()
    session.add(Audit(actor=account.id, action="normalizer_config", target="normalizer",
                      details=body.model_dump()))
    session.commit()
    return {"saved": True, **row.value}
