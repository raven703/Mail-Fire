"""Minimal authenticated regressions; writes only to an explicitly disposable DB."""
import io
import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.document_preview import render


@pytest.mark.parametrize("format", ["PNG", "JPEG", "TIFF"])
def test_passive_image_formats(format):
    data = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(data, format)
    assert render(data.getvalue(), '{}')["pages"] == 1


@pytest.mark.parametrize("mode,text", [(m, t) for m in ("detect", "augment") for t in
                         ("Обычный рабочий отчёт за понедельник", "В офисе б0мба\u200b")])
def test_normalizer_llm_payload(monkeypatch, mode, text):
    from app import llm_analyzer as llm

    class Session:
        def get(self, model, key):
            return SimpleNamespace(value={"enabled": True, "mode": mode, "sensitivity": "medium"})

        def scalars(self, query):
            return [SimpleNamespace(id="test", name="Тест")]

    @contextmanager
    def transaction():
        yield Session()

    sent = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            sent.append(kwargs["json"]["messages"][1]["content"])
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
                "choices": [{"message": {"content": '{"matches":[]}'}}]})

    monkeypatch.setattr(llm, "transaction", transaction)
    monkeypatch.setattr(llm, "config", lambda s: {**llm.DEFAULTS, "enabled": True,
                        "routing": "selected", "categories": ["test"], "model": "mock",
                        "allow_external_content": True, "base_url": "https://example.invalid"})
    monkeypatch.setattr(llm.httpx, "Client", Client)
    assert llm.analyze(text, []) == ([], [])
    assert text in sent[0]
    if mode == "augment" and "б0мба" in text:
        assert "бомба" in sent[0] and "ВОССТАНОВЛЕННЫЙ" in sent[0]
    else:
        assert sent[0] == text


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Disposable PostgreSQL only")
def test_accounts_csrf_revocation_and_model_protection():
    from app.db import transaction
    from app.main import app
    from app.models import MLModel

    with TestClient(app, base_url="https://testserver") as admin, TestClient(app, base_url="https://testserver") as other:
        login = admin.post('/api/login', json={"username": "admin", "password": "synthetic-test-password-only"})
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        username = 'stage1-' + uuid.uuid4().hex[:12]
        body = {"username": username, "password": "synthetic-stage1-password", "role": "observer", "originals": False}
        assert admin.post('/api/accounts', json=body).status_code == 403
        created = admin.post('/api/accounts', json=body, headers=headers)
        assert created.status_code == 200, created.text
        account_id = created.json()['id']
        login = other.post('/api/login', json={"username": username, "password": body['password']})
        assert login.status_code == 200
        other_headers = {"X-CSRF-Token": login.json()['csrf']}
        assert other.get('/api/accounts').status_code == 403
        assert other.get('/api/attachments/missing/viewer').status_code == 403
        assert other.put('/api/catalog/normalizer', headers=other_headers,
                         json={"enabled": True}).status_code == 403
        assert admin.delete('/api/accounts/' + account_id, headers=headers).status_code == 200
        assert other.get('/api/me').status_code == 401
        accounts = admin.get('/api/accounts').json()['items']
        own = next(a for a in accounts if a['username'] == 'admin')
        assert admin.delete('/api/accounts/' + own['id'], headers=headers).status_code == 409
        for mode in ('detect', 'augment'):
            assert admin.put('/api/catalog/normalizer', headers=headers,
                             json={"enabled": True, "mode": mode, "sensitivity": "high"}).status_code == 200
        assert admin.put('/api/catalog/normalizer', headers=headers,
                         json={"enabled": False, "mode": "invalid"}).status_code == 422
        with transaction() as session:
            model = MLModel(name='stage1-active', artifact=b'', metrics={}, active=True)
            session.add(model)
            session.flush()
            model_id = model.id
        assert admin.delete('/api/ml/models/' + model_id, headers=headers).status_code == 409
        with transaction() as session:
            session.get(MLModel, model_id).active = False
        assert admin.delete('/api/ml/models/' + model_id, headers=headers).status_code == 200


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Disposable PostgreSQL only")
def test_stored_ocr_limits_and_failed_preview(monkeypatch):
    from app import preview_api
    from app.db import transaction
    from app.mail import put_blob
    from app.main import app
    from app.models import Attachment, Message

    with transaction() as session:
        sha = put_blob(session, ('synthetic-invalid-preview-' + uuid.uuid4().hex).encode())
        message = Message(original_sha=sha, format='eml')
        session.add(message)
        session.flush()
        rows = [Attachment(message_id=message.id, blob_sha=sha, name=name, mime=mime,
                           status='ANALYZED', text='Сохранённый OCR-текст', details={})
                for name, mime in [('image.png', 'image/png'), ('unsafe.html', 'text/html')]]
        big_sha = put_blob(session, b'0' * (20 * 1024**2 + 1))
        rows.append(Attachment(message_id=message.id, blob_sha=big_sha, name='large.pdf',
                               mime='application/pdf', status='PARTIAL', text='', details={}))
        session.add_all(rows)
        session.flush()
        ids = [r.id for r in rows]
    calls = []

    def failed(operation, *args):
        calls.append(operation)
        raise ValueError('synthetic conversion failure')

    monkeypatch.setattr(preview_api, 'call', failed)
    with TestClient(app, base_url='https://testserver') as client:
        client.post('/api/login', json={"username": "admin", "password": "synthetic-test-password-only"})
        response = client.get('/api/attachments/' + ids[0] + '/viewer')
        assert response.json()['text'] == 'Сохранённый OCR-текст'
        assert calls == []  # Opening stored OCR does not invoke extraction or recognition.
        assert client.get('/api/attachments/' + ids[1] + '/page').status_code == 422
        assert client.get('/api/attachments/' + ids[2] + '/page').status_code == 413
        assert client.get('/api/attachments/' + ids[0] + '/page?page=0').status_code == 422
        assert client.get('/api/attachments/' + ids[0] + '/page?scale=20').status_code == 422