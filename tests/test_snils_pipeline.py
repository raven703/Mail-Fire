import io
from email.message import EmailMessage

import pytest
from docx import Document
from openpyxl import Workbook

from app.mail import parse_mail
from app.extraction import extract
from app.advanced_detectors import pii


@pytest.mark.parametrize("kind", ["body", "html", "docx", "xlsx"])
@pytest.mark.parametrize("number,verification", [("112233445-95", "confirmed"), ("112233445-96", "suspected")])
def test_email_and_attachments(kind, number, verification):
    text = "СНИЛС сотрудника: " + number
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "receiver@example.invalid"
    message.set_content(text if kind == "body" else "Кадровая карточка во вложении.")
    if kind != "body":
        stream = io.BytesIO()
        if kind == "docx":
            doc = Document()
            table = doc.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "СНИЛС сотрудника"
            table.cell(0, 1).text = number
            doc.save(stream)
        elif kind == "xlsx":
            book = Workbook()
            book.active.append(["СНИЛС сотрудника", number])
            book.save(stream)
        else:
            stream.write(("<table><tr><td>" + text + "</td></tr></table>").encode())
        message.add_attachment(stream.getvalue(), maintype="application", subtype="octet-stream", filename="card." + kind)
    parsed = parse_mail(message.as_bytes())
    text = parsed["text"]
    for name, mime, payload in parsed["attachments"]:
        extracted, status, details = extract(payload, name)
        assert status == "ANALYZED"
        text += "\n" + extracted
    hits = [f for f in pii(text) if f["category"] == "RU_SNILS"]
    assert hits and all(h["verification"] == verification for h in hits)