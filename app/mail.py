import hashlib
import os
import tempfile
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.models import Blob, ImportRecord, Job, MailEvent, Message


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_blob(session, data):
    digest = sha(data)
    session.execute(insert(Blob).values(sha=digest, data=data, size=len(data)).on_conflict_do_nothing())
    return digest


def format_of(data):
    if data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        return "msg"
    message = BytesParser(policy=policy.default).parsebytes(data, headersonly=True)
    if not any(message.get(h) for h in ("From", "To", "Subject", "Message-ID")):
        raise ValueError("Не распознан EML/MSG")
    return "eml"


def parse_mail(data):
    kind = format_of(data)
    if kind == "msg":
        import extract_msg

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "message.msg")
            with open(path, "wb") as stream:
                stream.write(data)
            with extract_msg.openMsg(path) as msg:
                attachments = []
                for item in msg.attachments:
                    payload = item.data
                    if not isinstance(payload, bytes):
                        raise ValueError("Вложенный Outlook объект требует отдельного парсера")
                    attachments.append(
                        (
                            item.longFilename or item.shortFilename or "attachment",
                            "application/octet-stream",
                            payload,
                        )
                    )
                return dict(
                    subject=msg.subject or "",
                    sender=getaddresses([msg.sender or ""])[0][1] if msg.sender else "",
                    recipients=[a for _, a in getaddresses([msg.to or "", msg.cc or "", msg.bcc or ""])],
                    headers=dict(msg.header.items()) if msg.header else {},
                    text=msg.body or "",
                    attachments=attachments,
                )
    msg = BytesParser(policy=policy.default).parsebytes(data)
    texts, attachments = [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b""
        if part.get_filename() or part.get_content_maintype() != "text":
            attachments.append((part.get_filename() or "inline", part.get_content_type(), payload))
        else:
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            texts.append(
                BeautifulSoup(text, "html.parser").get_text(" ")
                if part.get_content_type() == "text/html"
                else text
            )
    return dict(
        subject=str(msg.get("Subject", "")),
        sender=getaddresses([str(msg.get("From", ""))])[0][1] if msg.get("From") else "",
        recipients=[
            address.addr_spec
            for key in ("To", "Cc", "Bcc")
            for header in msg.get_all(key, [])
            for address in getattr(header, "addresses", ())
        ],
        headers={k: str(v) for k, v in msg.items()},
        text="\n".join(texts),
        attachments=attachments,
    )


def ingest(session, data, source, source_key, name, envelope=None):
    if len(data) > settings().max_message_bytes:
        raise ValueError("Превышен размер письма")
    session.execute(
        __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": source_key}
    )
    existing = session.scalar(select(ImportRecord).where(ImportRecord.source_key == source_key))
    if existing:
        return existing
    kind = format_of(data)
    digest = put_blob(session, data)
    message = session.scalar(select(Message).where(Message.original_sha == digest))
    duplicate = message is not None
    if not message:
        session.execute(
            __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": digest}
        )
        message = session.scalar(select(Message).where(Message.original_sha == digest))
        if not message:
            message = Message(original_sha=digest, format=kind)
            session.add(message)
            session.flush()
            session.add(Job(kind="analyze", payload={"message_id": message.id}))
    event = MailEvent(message_id=message.id, source=source, source_key=source_key, envelope=envelope or {})
    session.add(event)
    record = ImportRecord(
        source_key=source_key, name=name, status="SAVED", message_id=message.id, duplicate=duplicate
    )
    session.add(record)
    session.flush()
    # New delivery context must be evaluated even if content was analyzed earlier.
    session.add(Job(kind="evaluate", payload={"event_id": event.id}))
    return record
