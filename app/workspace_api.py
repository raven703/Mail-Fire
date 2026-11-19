"""Analyst workspace: bounded, permission-aware PostgreSQL queries."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select

from app.api import admin, analyst, db, serialize, user
from app.models import (
    Account,
    Attachment,
    Audit,
    Blob,
    Comment,
    Content,
    Incident,
    Job,
    MailEvent,
    Message,
    Policy,
    Setting,
)

router = APIRouter(prefix="/api/workspace", tags=["Analyst workspace"])
OPEN = ["NEW", "ASSIGNED", "REVIEW", "REOPENED"]


def period(start: datetime | None = None, end: datetime | None = None):
    end = end or datetime.now(UTC)
    start = start or end - timedelta(hours=24)
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise HTTPException(422, "Укажите корректный период с часовым поясом")
    return start.astimezone(UTC).replace(tzinfo=None), end.astimezone(UTC).replace(tzinfo=None)


def severity(risk):
    return "HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW"


def risk_filter(column, level):
    if level == "HIGH":
        return column >= 70
    if level == "MEDIUM":
        return (column >= 40) & (column < 70)
    if level == "LOW":
        return column < 40
    raise HTTPException(422, "Неизвестная критичность")


def incident_query():
    return (
        select(Incident, Message, Policy.name, Account.username)
        .join(MailEvent, MailEvent.id == Incident.event_id)
        .join(Message, Message.id == MailEvent.message_id)
        .outerjoin(Policy, Policy.id == Incident.policy_id)
        .outerjoin(Account, Account.id == Incident.assignee)
    )


def incident_row(row, sensitive):
    item, mail, policy, assignee = row
    result = serialize(item)
    result.update(
        message_id=mail.id,
        subject=mail.subject,
        sender=mail.sender,
        recipients=mail.recipients,
        category=", ".join(h.get("name", "") for h in (item.policy_hits or []) if h.get("active")) or policy or "Исторические политики",
        policies=[{"id": h.get("policy_id"), "name": h.get("name"), "risk": h.get("risk"), "active": h.get("active", True), "version": h.get("version")} for h in (item.policy_hits or [])],
        analyst=assignee,
        severity=severity(item.risk),
    )
    if not sensitive:
        result.pop("findings", None)
    return result


@router.get("/messages")
def messages(
    start: datetime | None = None,
    end: datetime | None = None,
    q: str = Query("", max_length=500),
    direction: str = "",
    source: str = "",
    status: str = "",
    incidents: str = "",
    severity: str = "",
    attachments: str = "",
    mime: str = "",
    sort: str = "date",
    order: str = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    account=Depends(user),
    session=Depends(db),
):
    begin, finish = period(start, end)
    counts = (
        select(
            MailEvent.message_id.label("mid"),
            func.count(Incident.id).label("incidents"),
            func.max(Incident.risk).label("risk"),
        )
        .join(Incident, Incident.event_id == MailEvent.id)
        .group_by(MailEvent.message_id)
        .subquery()
    )
    files = (
        select(Attachment.message_id.label("mid"), func.count().label("attachments"))
        .group_by(Attachment.message_id)
        .subquery()
    )
    query = (
        select(
            Message,
            func.coalesce(counts.c.incidents, 0),
            counts.c.risk,
            func.coalesce(files.c.attachments, 0),
        )
        .outerjoin(counts, counts.c.mid == Message.id)
        .outerjoin(files, files.c.mid == Message.id)
        .where(Message.created_at >= begin, Message.created_at < finish)
    )
    if q.strip():
        term = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions = [
            Message.subject.ilike(term),
            Message.sender.ilike(term),
            cast(Message.recipients, String).ilike(term),
            Message.id == q,
            cast(Message.headers, String).ilike(term),
        ]
        if account.originals:
            conditions.extend(
                [
                    Message.content_id.in_(
                        select(Content.id).where(
                            or_(
                                Content.text.ilike(term),
                                func.to_tsvector("simple", Content.text).op("@@")(
                                    func.plainto_tsquery("simple", q)
                                ),
                            )
                        )
                    ),
                    Message.id.in_(select(Attachment.message_id).where(Attachment.name.ilike(term))),
                ]
            )
        query = query.where(or_(*conditions))
    if direction:
        query = query.where(
            select(MailEvent.id)
            .where(MailEvent.message_id == Message.id, MailEvent.direction == direction)
            .exists()
        )
    if source:
        if source in {"eml", "msg"}:
            query = query.where(Message.format == source)
        else:
            query = query.where(
                select(MailEvent.id)
                .where(MailEvent.message_id == Message.id, MailEvent.source == source)
                .exists()
            )
    if status:
        query = query.where(Message.status == status)
    if incidents:
        query = query.where(counts.c.incidents > 0 if incidents == "yes" else counts.c.mid.is_(None))
    if severity:
        query = query.where(risk_filter(counts.c.risk, severity))
    if attachments:
        query = query.where(files.c.attachments > 0 if attachments == "yes" else files.c.mid.is_(None))
    if mime:
        query = query.where(
            select(Attachment.id)
            .where(Attachment.message_id == Message.id, Attachment.mime.ilike("%" + mime[:100] + "%"))
            .exists()
        )
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    column = {
        "date": Message.created_at,
        "risk": counts.c.risk,
        "subject": Message.subject,
        "sender": Message.sender,
    }.get(sort)
    if column is None or order not in {"asc", "desc"}:
        raise HTTPException(422, "Некорректная сортировка")
    rows = list(
        session.execute(
            query.order_by((column.asc() if order == "asc" else column.desc()).nulls_last(), Message.id)
            .offset(offset)
            .limit(limit)
        )
    )
    ids = [r[0].id for r in rows]
    events = {}
    for event in session.scalars(
        select(MailEvent).where(MailEvent.message_id.in_(ids)).order_by(MailEvent.created_at)
    ):
        events.setdefault(event.message_id, event)
    items = []
    for mail, count, risk, file_count in rows:
        event = events.get(mail.id)
        items.append(
            dict(
                id=mail.id,
                created_at=mail.created_at,
                subject=mail.subject,
                sender=mail.sender,
                recipients=mail.recipients,
                status=mail.status,
                incident_count=count,
                severity=globals()["severity"](risk) if risk is not None else None,
                attachment_count=file_count,
                direction=event.direction if event else "UNKNOWN",
                source=event.source if event else mail.format,
            )
        )
    return {"items": items, "total": total}


@router.get("/incidents")
def incidents(
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str = "",
    status: str = "open",
    q: str = Query("", max_length=500),
    category: str = "",
    sender: str = "",
    recipient: str = "",
    assignee: str = "",
    direction: str = "",
    source: str = "",
    sort: str = "date",
    order: str = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    account=Depends(user),
    session=Depends(db),
):
    begin, finish = period(start, end)
    query = incident_query().where(Incident.created_at >= begin, Incident.created_at < finish)
    if status == "open":
        query = query.where(Incident.status.in_(OPEN))
    elif status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(risk_filter(Incident.risk, severity))
    for value, column in [
        (sender, Message.sender),
        (recipient, cast(Message.recipients, String)),
        (assignee, Account.username),
        (category, Policy.name),
    ]:
        if value:
            query = query.where(column.ilike("%" + value[:200] + "%"))
    if direction:
        query = query.where(MailEvent.direction == direction)
    if source:
        query = query.where(MailEvent.source == source)
    if q:
        query = query.where(
            or_(
                Message.subject.ilike("%" + q + "%"),
                Message.sender.ilike("%" + q + "%"),
                Policy.name.ilike("%" + q + "%"),
                Incident.id == q,
            )
        )
    column = {"date": Incident.created_at, "risk": Incident.risk, "sender": Message.sender}.get(sort)
    if column is None or order not in {"asc", "desc"}:
        raise HTTPException(422)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(column.asc() if order == "asc" else column.desc(), Incident.id)
        .offset(offset)
        .limit(limit)
    )
    return {"items": [incident_row(r, account.originals) for r in rows], "total": total}


@router.get("/overview")
def overview(
    start: datetime | None = None, end: datetime | None = None, account=Depends(user), session=Depends(db)
):
    begin, finish = period(start, end)
    within = (Incident.created_at >= begin) & (Incident.created_at < finish)
    levels = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    timeline = {}
    interval = "hour" if finish - begin <= timedelta(days=2) else "day"
    bucket_expr = func.date_trunc(interval, Incident.created_at)
    for bucket, risk, count in session.execute(
        select(bucket_expr, Incident.risk, func.count())
        .where(within)
        .group_by(bucket_expr, Incident.risk)
        .order_by(bucket_expr)
    ):
        level = severity(risk)
        levels[level] += count
        key = bucket.isoformat() + "Z"
        timeline.setdefault(key, {"time": key, "HIGH": 0, "MEDIUM": 0, "LOW": 0})[level] += count
    queues = dict(session.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    recent = session.execute(
        incident_query().where(within).order_by(Incident.risk.desc(), Incident.created_at.desc()).limit(8)
    )
    # One incident may match multiple policies; policy hit counts are not
    # the same as the number of unique incidents.
    categories = [
        dict(name=name, count=count)
        for name, count in session.execute(
            __import__("sqlalchemy").text("""
                SELECT hit->>'name' AS name, count(*) AS count
                FROM incidents i
                CROSS JOIN LATERAL jsonb_array_elements(i.policy_hits) AS hit
                WHERE i.created_at >= :begin AND i.created_at < :finish
                  AND hit->>'name' IS NOT NULL
                GROUP BY hit->>'name' ORDER BY count(*) DESC
            """),
            {"begin": begin, "finish": finish},
        )
    ]
    return {
        "categories": categories,
        "incidents": sum(levels.values()),
        "review": session.scalar(
            select(func.count()).select_from(Incident).where(within, Incident.status.in_(OPEN))
        ),
        "analyzed": session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.created_at >= begin, Message.created_at < finish, Message.status == "ANALYZED")
        ),
        "active_jobs": sum(queues.get(s, 0) for s in ["PENDING", "RUNNING"]),
        "levels": levels,
        "timeline": list(timeline.values()),
        "interval": interval,
        "recent": [incident_row(r, False) for r in recent],
        "queues": queues,
        "health": {
            "PostgreSQL": "OK",
            "Очереди": "ERROR" if queues.get("DEAD") else "OK",
            "BCC / импорт": "UNKNOWN",
            "OCR / ML": "UNKNOWN",
            "SIEM": "UNKNOWN",
        },
    }


@router.get("/messages/{message_id}")
def message_detail(message_id: str, account=Depends(user), session=Depends(db)):
    mail = session.get(Message, message_id)
    if not mail:
        raise HTTPException(404)
    result = serialize(mail)
    result["events"] = [
        serialize(e) for e in session.scalars(select(MailEvent).where(MailEvent.message_id == mail.id))
    ]
    result["incidents"] = [
        incident_row(r, account.originals)
        for r in session.execute(incident_query().where(Message.id == mail.id))
    ]
    result["history"] = [
        serialize(r)
        for r in session.scalars(
            select(Audit).where(Audit.target == mail.id).order_by(Audit.created_at.desc()).limit(100)
        )
    ]
    if account.originals:
        content = session.get(Content, mail.content_id) if mail.content_id else None
        result["text"] = content.text if content else ""
        result["findings"] = content.analysis.get("findings", []) if content else []
        result["attachments"] = []
        for file in session.scalars(select(Attachment).where(Attachment.message_id == mail.id)):
            data = serialize(file)
            data["size"] = session.scalar(select(Blob.size).where(Blob.sha == file.blob_sha))
            result["attachments"].append(data)
    else:
        result.pop("headers", None)
        result.pop("error", None)
        for e in result["events"]:
            e.pop("envelope", None)
    session.add(Audit(actor=account.id, action="view_message", target=mail.id))
    session.commit()
    return result


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: str, account=Depends(user), session=Depends(db)):
    row = session.execute(incident_query().where(Incident.id == incident_id)).first()
    if not row:
        raise HTTPException(404)
    result = incident_row(row, account.originals)
    result["policy_hits"] = row[0].policy_hits or []
    result["comments"] = [
        dict(id=c.id, text=c.text, created_at=c.created_at, username=name)
        for c, name in session.execute(
            select(Comment, Account.username)
            .join(Account, Account.id == Comment.account_id)
            .where(Comment.incident_id == incident_id)
            .order_by(Comment.created_at)
        )
    ]
    result["history"] = [
        serialize(r)
        for r in session.scalars(
            select(Audit).where(Audit.target == incident_id).order_by(Audit.created_at.desc()).limit(100)
        )
    ]
    result["related"] = [
        incident_row(r, False)
        for r in session.execute(
            incident_query().where(Message.id == row[1].id, Incident.id != incident_id).limit(50)
        )
    ]
    return result


@router.get("/analysts")
def analysts(account=Depends(user), session=Depends(db)):
    return {
        "items": [
            dict(id=a.id, username=a.username)
            for a in session.scalars(
                select(Account).where(Account.enabled.is_(True), Account.role.in_(["admin", "analyst"]))
            )
        ]
    }


class Assignment(BaseModel):
    assignee: str | None = None


@router.put("/incidents/{incident_id}/assignee")
def assign(incident_id: str, body: Assignment, account=Depends(analyst), session=Depends(db)):
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404)
    target = session.get(Account, body.assignee) if body.assignee else None
    if body.assignee and (not target or not target.enabled or target.role not in {"admin", "analyst"}):
        raise HTTPException(422, "Выберите действующего аналитика")
    incident.assignee = body.assignee
    session.add(
        Audit(actor=account.id, action="assign_incident", target=incident_id, details=body.model_dump())
    )
    session.commit()
    return {"saved": True}


class Preference(BaseModel):
    theme: str = Field(pattern="^(light|dark|system)$")


@router.get("/preferences")
def preferences(account=Depends(user), session=Depends(db)):
    row = session.get(Setting, "ui:" + account.id)
    return row.value if row else {"theme": "system"}


@router.put("/preferences")
def save_preferences(body: Preference, account=Depends(user), session=Depends(db)):
    key = "ui:" + account.id
    row = session.get(Setting, key)
    if not row:
        row = Setting(key=key, value={})
        session.add(row)
    row.value = body.model_dump()
    session.commit()
    return row.value


class PolicyBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    shadow: bool = False
    priority: int = Field(default=10, ge=0, le=10000)
    min_risk: int = Field(default=40, ge=0, le=100)
    min_count: int = Field(default=1, ge=1, le=1000)
    category_match: str = Field(default="any", pattern="^(any|all)$")
    categories: list[str] = Field(default_factory=list, max_length=50)
    direction: list[str] = Field(default_factory=list, max_length=4)
    senders: list[str] = Field(default_factory=list, max_length=200)


def persist_policy(body, session, account, row):
    from app.categories import available_categories

    if body.category_match == "all" and not body.categories:
        raise HTTPException(422, "Для режима «Все категории» выберите хотя бы одну категорию")
    if not available_categories(session, body.categories, allow_label=False):
        raise HTTPException(422, "Категория неизвестна, архивирована или предназначена только для ML")
    if any(d not in {"INBOUND", "OUTBOUND", "UNKNOWN", "INTERNAL"} for d in body.direction):
        raise HTTPException(422, "Неизвестное направление")
    before = serialize(row) if row.id else None
    row.name, row.enabled, row.shadow, row.priority = body.name, body.enabled, body.shadow, body.priority
    row.conditions = body.model_dump(include={"min_risk", "min_count", "category_match", "categories", "direction", "senders"})
    row.version = (row.version or 0) + 1
    session.add(row)
    session.flush()
    session.add(
        Audit(
            actor=account.id,
            action="policy_save",
            target=row.id,
            details=jsonable_encoder({"before": before, "after": serialize(row)}),
        )
    )
    session.commit()
    return serialize(row)


@router.post("/policies")
def create_policy(body: PolicyBody, account=Depends(admin), session=Depends(db)):
    return persist_policy(body, session, account, Policy())


@router.put("/policies/{policy_id}")
def update_policy(policy_id: str, body: PolicyBody, account=Depends(admin), session=Depends(db)):
    row = session.get(Policy, policy_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    return persist_policy(body, session, account, row)


@router.get("/policies/{policy_id}/history")
def policy_history(policy_id: str, account=Depends(user), session=Depends(db)):
    return {
        "items": [
            serialize(r)
            for r in session.scalars(
                select(Audit)
                .where(Audit.target == policy_id, Audit.action == "policy_save")
                .order_by(Audit.created_at.desc())
                .limit(100)
            )
        ]
    }

@router.post("/policies/{policy_id}/archive")
def archive_policy(policy_id: str, account=Depends(admin), session=Depends(db)):
    row = session.get(Policy, policy_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    row.enabled = False
    row.archived = True
    session.add(Audit(actor=account.id, action="policy_archive", target=row.id, details={"snapshot": jsonable_encoder(serialize(row))}))
    session.commit()
    return {"archived": True}


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: str, account=Depends(admin), session=Depends(db)):
    """Delete from active catalog without destroying historical incident evidence."""
    row = session.get(Policy, policy_id, with_for_update=True)
    if not row:
        raise HTTPException(404)
    snapshot = jsonable_encoder(serialize(row))
    # Historical incidents keep policy_hits as an immutable snapshot, and the
    # representative nullable FK is cleared before deleting the policy row.
    session.execute(
        __import__("sqlalchemy").update(Incident)
        .where(Incident.policy_id == policy_id).values(policy_id=None)
    )
    session.add(Audit(actor=account.id, action="policy_delete", target=policy_id,
                      details={"snapshot": snapshot}))
    session.delete(row)
    session.commit()
    return {"deleted": True, "id": policy_id}
