import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires PostgreSQL")


def test_model_publication_and_rollback():
    from fastapi.testclient import TestClient
    from test_ml import examples

    from app.db import transaction
    from app.main import app
    from app.ml import train
    from app.models import MLModel

    artifact, metrics, eligible = train(examples())
    with transaction() as db:
        first = MLModel(name="synthetic-first", artifact=artifact, metrics=metrics, eligible=eligible)
        second = MLModel(name="synthetic-second", artifact=artifact, metrics=metrics, eligible=eligible)
        rejected = MLModel(name="synthetic-rejected", artifact=artifact, metrics={}, eligible=False)
        db.add_all([first, second, rejected])
        db.flush()
        ids = [first.id, second.id, rejected.id]
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"username": "admin", "password": "synthetic-test-password-only"}
        )
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        for model_id in [ids[0], ids[1], ids[0]]:
            assert client.post(f"/api/ml/models/{model_id}/publish", headers=headers).status_code == 200
        assert client.post(f"/api/ml/models/{ids[2]}/publish", headers=headers).status_code == 409
        result = client.post(
            "/api/ml/infer", headers=headers, json={"text": "confidential finance forecast revenue costs"}
        )
        assert result.json()["model_id"] == ids[0]
    with transaction() as db:
        for model_id in ids:
            db.delete(db.get(MLModel, model_id))
