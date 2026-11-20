import io
from email.message import EmailMessage

import pytest
from docx import Document
from openpyxl import Workbook

from app.mail import parse_mail
from app.extraction import extract
from app.advanced_detectors import pii


@pytest.mark.parametrize("kind", ["body", "html", "docx", "xlsx"])
def test_mime_extraction_to_passport_detector(kind):
    text = "Паспорт РФ. Серия 58 23, номер 792614"
    message = EmailMessage()
    message["From"] = "test@example.invalid"
    message["To"] = "receiver@example.invalid"
    message.set_content(text if kind == "body" else "Смотрите вложение.")
    if kind != "body":
        stream = io.BytesIO()
        if kind == "docx":
            doc = Document()
            table = doc.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Паспорт РФ. Серия 58 23"
            table.cell(0, 1).text = "номер 792614"
            doc.save(stream)
        elif kind == "xlsx":
            book = Workbook()
            book.active.append(["Паспорт РФ", "Серия", "Номер"])
            book.active.append(["", "58 23", "792614"])
            book.save(stream)
        else:
            stream.write(f"<table><tr><td>{text}</td></tr></table>".encode())
        message.add_attachment(stream.getvalue(), maintype="application", subtype="octet-stream", filename="sample." + kind)
    parsed = parse_mail(message.as_bytes())
    combined = parsed["text"]
    for name, mime, payload in parsed["attachments"]:
        text, status, details = extract(payload, name)
        assert status == "ANALYZED"
        combined += "\n" + text
    assert any(f["category"] == "RU_PASSPORT" for f in pii(combined))