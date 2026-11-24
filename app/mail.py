import hashlib
import os
import tempfile
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from bs4 import BeautifulSoup

from app.config import settings


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()




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


def classify_direction(sender, recipients, internal_domains):
    """Conservative direction inference based only on message addresses.

    SMTP BCC collector recipient is not necessarily an original recipient.
    """
    domains = {d.strip().lower().lstrip("@") for d in internal_domains.split(",") if d.strip()}
    if not domains:
        return "UNKNOWN"

    def is_internal(address):
        address = (address or "").strip().lower()
        if address.count("@") != 1:
            return None
        domain = address.rsplit("@", 1)[1]
        return domain in domains or any(domain.endswith("." + d) for d in domains)

    src = is_internal(sender)
    dst = {is_internal(addr) for addr in recipients if addr}
    if src is None or not dst or None in dst:
        return "UNKNOWN"
    if src and False in dst:
        return "OUTBOUND"
    if not src and True in dst:
        return "INBOUND"
    if src and dst == {True}:
        return "INTERNAL"
    return "UNKNOWN"
