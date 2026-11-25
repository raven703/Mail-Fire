from app.advanced_detectors import pii, snils_valid, static_scan


def test_real_presidio_russian_recognizers():
    assert snils_valid("112-233-445 95")
    assert not snils_valid("112-233-445 96")
    from app.detectors import detect
    text = "ИНН 7707083893; СНИЛС 112-233-445 95; паспорт 45 01 123456"
    findings = pii(text) + detect(text)
    assert {"INN", "RU_SNILS", "RU_PASSPORT"} <= {r["category"] for r in findings}
    assert not any(r["category"] == "RU_SNILS" for r in pii("112-233-445 96"))


def test_real_yara_script_and_clean_text():
    assert static_scan(b"powershell -EncodedCommand QUJDRA==", "test.ps1")["findings"]
    assert not static_scan(b"Annual financial meeting agenda", "clean.txt")["findings"]


def test_real_gitleaks_when_installed():
    import shutil

    import pytest

    from app.secret_scan import scan

    if not shutil.which("gitleaks"):
        pytest.skip("Gitleaks binary not installed")
    assert scan(b'api_key = "synthetic-AbC123456789XYZabcdefgh987654321"')["findings"]
    assert not scan(b"No credentials in this meeting agenda")["findings"]
