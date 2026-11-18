"""Audit regressions for direction inference and archive scanning."""

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


def test_archive_members_scanned_without_binary_response():
    from app.extraction import extract

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("secret.txt", "powershell -EncodedCommand QUJDRA==")
        archive.writestr("unknown.bin", b"\x01\x02")
    text, status, details = extract(stream.getvalue(), "mail.zip")
    assert "powershell -EncodedCommand QUJDRA==" in text
    assert "scan_members" not in details
    assert any(f["source"] == "yara" for f in details["findings"])
    assert status == "PARTIAL"


def test_nested_zip_scan_has_no_binary_payload():
    from app.sandbox import local_call

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("command.ps1", "powershell -EncodedCommand QUJDRA==")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nested.zip", inner.getvalue())
    result = local_call("extract", outer.getvalue(), "outer.zip")
    assert any(f["source"] == "yara" for f in result["details"]["findings"])
    assert "scan_members" not in str(result)


def test_parser_output_limit(monkeypatch):
    import pytest

    from app.config import settings
    from app.sandbox import local_call

    monkeypatch.setattr(settings(), "parser_response_bytes", 20)
    with pytest.raises(ValueError, match="output limit"):
        local_call("extract", b"a" * 100, "test.txt")
