"""Audit regressions for direction inference and archive scanning."""
import base64
import io
import zipfile

from app.mail import classify_direction


def test_direction_classification():
    domains = "company.ru,corp.example"
    assert classify_direction("a@company.ru", ["b@other.org"], domains) == "OUTBOUND"
    assert classify_direction("a@other.org", ["b@company.ru"], domains) == "INBOUND"
    assert classify_direction("a@company.ru", ["b@company.ru"], domains) == "INTERNAL"
    assert classify_direction("a@company.ru", ["b@company.ru", "c@other.org"], domains) == "OUTBOUND"
    assert classify_direction("a@company.ru", [], domains) == "UNKNOWN"
    assert classify_direction("a@company.ru", ["b@other.org"], "") == "UNKNOWN"
    assert classify_direction("bad-address", ["b@company.ru"], domains) == "UNKNOWN"


def test_archive_members_exposed_for_separate_scanning():
    from app.extraction import extract

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("secret.txt", "synthetic token")
        archive.writestr("unknown.bin", b"\x01\x02")
    text, status, details = extract(stream.getvalue(), "mail.zip")
    assert "synthetic token" in text
    assert len(details["scan_members"]) == 2
    assert base64.b64decode(details["scan_members"][0]["data"]) == b"synthetic token"
    assert status == "PARTIAL"
