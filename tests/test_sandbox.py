from app.sandbox import call


def test_network_denied_and_secrets_removed(monkeypatch):
    from app.config import settings

    settings()
    monkeypatch.setenv("DATABASE_URL", "secret-must-not-escape")
    result = call("probe", b"")
    assert result == {"network_denied": True, "database_secret": None}


def test_real_sandbox_mail_and_extraction():
    from test_core import synthetic_mail

    parsed = call("mail", synthetic_mail(100))
    assert len(parsed["recipients"]) == 100
    assert isinstance(parsed["attachments"][0][2], bytes)
    assert call("extract", b"synthetic", "test.txt")["text"] == "synthetic"
