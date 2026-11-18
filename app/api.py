import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from app.config import settings
from app.db import Session, transaction
from app.mail import ingest, sha
from app.models import (
    Account,
    Address,
    Audit,
    Blob,
    Comment,
    Content,
    Diagnostic,
    ImportRecord,
    Incident,
    Job,
    LoginSession,
    MailEvent,
    Message,
    Metric,
    Policy,
    now,
)

app = FastAPI(title="Mail Fire", version="0.1.0")


def db():
    with Session() as session:
        yield session


def user(request: Request, session=Depends(db)):
    token = request.cookies.get("session", "")
    login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not login or login.expires_at < now().replace(tzinfo=None):
        raise HTTPException(401, "Требуется вход")
    account = session.get(Account, login.account_id)
    if not account or not account.enabled:
        raise HTTPException(401, "Доступ отключён")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-csrf-token") != token:
        raise HTTPException(403, "CSRF")
    return account


def analyst(account=Depends(user)):
    if account.role not in {"admin", "analyst"}:
        raise HTTPException(403, "Недостаточно прав")
    return account


def admin(account=Depends(user)):
    if account.role != "admin":
        raise HTTPException(403, "Требуется администратор")
    return account


class Login(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=1024)


@app.get("/api/health")
def health(session=Depends(db)):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/login")
def login(body: Login, response: Response, session=Depends(db)):
    account = session.scalar(select(Account).where(Account.username == body.username))
    try:
        if not account or not account.enabled:
            raise ValueError()
        PasswordHasher().verify(account.password_hash, body.password)
    except Exception:
        raise HTTPException(401, "Неверные учётные данные")
    token = secrets.token_urlsafe(48)
    session.add(
        LoginSession(
            token_hash=sha(token.encode()),
            account_id=account.id,
            expires_at=now() + timedelta(hours=settings().session_hours),
        )
    )
    session.add(Audit(actor=account.id, action="login", target=account.id))
    session.commit()
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=settings().session_hours * 3600,
    )
    return {"csrf": token, "role": account.role, "username": account.username}


@app.get("/api/me")
def me(account=Depends(user)):
    return {"username": account.username, "role": account.role, "originals": account.originals}


@app.post("/api/logout")
def logout(request: Request, response: Response, account=Depends(user), session=Depends(db)):
    row = session.get(LoginSession, sha(request.cookies["session"].encode()))
    session.delete(row)
    session.commit()
    response.delete_cookie("session")
    return {"ok": True}


def serialize(row):
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in {"password_hash", "data", "artifact", "token_hash"}
    }


RESOURCES = {
    "messages": Message,
    "events": MailEvent,
    "imports": ImportRecord,
    "jobs": Job,
    "incidents": Incident,
    "policies": Policy,
    "addresses": Address,
    "audit": Audit,
    "logs": Diagnostic,
    "metrics": Metric,
}


@app.get("/api/list/{resource}")
def listing(
    resource: str, offset: int = 0, limit: int = 50, q: str = "", account=Depends(user), session=Depends(db)
):
    model = RESOURCES.get(resource)
    if not model or offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(400, "Некорректный запрос")
    if resource in {"audit", "logs"} and account.role != "admin":
        raise HTTPException(403)
    query = select(model)
    if q and model is Message:
        query = query.where(Message.subject.ilike("%" + q[:200] + "%"))
    count = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(model.created_at.desc()).offset(offset).limit(limit))
    items = [serialize(r) for r in rows]
    if not account.originals:
        for item in items:
            item.pop("findings", None)
            item.pop("headers", None)
            item.pop("envelope", None)
    return {"total": count, "items": items}


@app.post("/api/import")
async def upload(files: list[UploadFile], account=Depends(analyst)):
    if len(files) > 100:
        raise HTTPException(413)
    results = []
    for file in files:
        data = await file.read(settings().max_message_bytes + 1)
        try:
            with transaction() as session:
                record = ingest(session, data, "web", "web:" + sha(data), file.filename or "upload")
                results.append(serialize(record))
        except Exception as exc:
            results.append({"name": file.filename, "status": "FAILED", "error": type(exc).__name__})
    return results


@app.get("/api/messages/{message_id}")
def message(message_id: str, account=Depends(user), session=Depends(db)):
    row = session.get(Message, message_id)
    if not row:
        raise HTTPException(404)
    content = session.get(Content, row.content_id) if row.content_id else None
    session.add(Audit(actor=account.id, action="view_message", target=row.id))
    session.commit()
    result = serialize(row)
    # Message bodies/findings require the explicit sensitive-data permission.
    if account.originals:
        result["text"] = content.text if content else ""
        result["analysis"] = content.analysis if content else {}
    return result


@app.get("/api/messages/{message_id}/original")
def original(message_id: str, account=Depends(user), session=Depends(db)):
    if not account.originals:
        raise HTTPException(403)
    row = session.get(Message, message_id)
    if not row:
        raise HTTPException(404)
    data = session.get(Blob, row.original_sha).data
    session.add(Audit(actor=account.id, action="download_original", target=row.id))
    session.commit()
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="message.{row.format}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/messages/{message_id}/reanalyze")
def reanalyze(message_id: str, account=Depends(analyst), session=Depends(db)):
    if not session.get(Message, message_id):
        raise HTTPException(404)
    session.add(Job(kind="analyze", payload={"message_id": message_id}, priority=50))
    session.add(Audit(actor=account.id, action="reanalyze", target=message_id))
    session.commit()
    return {"queued": True}


class Decision(BaseModel):
    status: str
    comment: str = Field(default="", max_length=10000)


@app.patch("/api/incidents/{incident_id}")
def decision(incident_id: str, body: Decision, account=Depends(analyst), session=Depends(db)):
    if body.status not in {"NEW", "ASSIGNED", "REVIEW", "CONFIRMED", "FALSE_POSITIVE", "CLOSED", "REOPENED"}:
        raise HTTPException(422)
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404)
    incident.status = body.status
    if body.comment:
        session.add(Comment(incident_id=incident.id, account_id=account.id, text=body.comment))
    session.add(
        Audit(
            actor=account.id, action="incident_decision", target=incident.id, details={"status": body.status}
        )
    )
    session.commit()
    return serialize(incident)


@app.get("/api/monitor")
def monitor(account=Depends(user), session=Depends(db)):
    return {
        "messages": session.scalar(select(func.count()).select_from(Message)),
        "events": session.scalar(select(func.count()).select_from(MailEvent)),
        "incidents": session.scalar(select(func.count()).select_from(Incident)),
        "queues": [
            {"status": status, "count": count}
            for status, count in session.execute(select(Job.status, func.count()).group_by(Job.status))
        ],
        "database_bytes": session.scalar(text("SELECT pg_database_size(current_database())")),
    }


@app.post("/api/jobs/{job_id}/retry")
def retry(job_id: str, account=Depends(admin), session=Depends(db)):
    job = session.get(Job, job_id, with_for_update=True)
    if not job:
        raise HTTPException(404)
    if job.status not in {"DEAD", "DONE"}:
        raise HTTPException(409, "Задание ещё активно")
    job.status, job.attempts, job.available_at = "PENDING", 0, now()
    session.commit()
    return {"queued": True}
