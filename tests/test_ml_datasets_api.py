"""PostgreSQL-only dataset import and review regressions (disposable DB)."""
import json
import os
import uuid

import pytest

pytestmark=pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"),reason="Disposable PostgreSQL required")


def test_dataset_import_review_and_access_controls():
    from fastapi.testclient import TestClient
    from sqlalchemy import delete

    from app.db import transaction
    from app.main import app
    from app.models import MLDataset, TrainingExample

    nonce=uuid.uuid4().hex
    blob="\n".join(json.dumps({
        "text":f"Synthetic test for finance classification {nonce} sample {i}",
        "labels":["finance"] if i%2 else [],
    }) for i in range(4)).encode()
    with TestClient(app,base_url="https://testserver") as client:
        assert client.get("/api/ml/datasets").status_code==401
        login=client.post("/api/login",json={"username":"admin","password":"synthetic-test-password-only"})
        assert login.status_code==200,login.text
        headers={"X-CSRF-Token":login.json()["csrf"]}
        params={"name":"Synthetic-"+nonce,"source":"external-llm",
                "label_mapping":json.dumps({"finance":"CONFIDENTIAL"})}
        files={"file":("examples.jsonl",blob,"application/x-ndjson")}
        assert client.post("/api/ml/datasets/import",data=params,files=files).status_code==403
        result=client.post("/api/ml/datasets/import",headers=headers,data=params,files=files)
        assert result.status_code==201,result.text
        dataset_id=result.json()["id"]
        try:
            assert result.json()["example_count"]==4
            second=client.post("/api/ml/datasets/import",headers=headers,data=params,files=files)
            assert second.status_code==409,second.text
            examples=client.get(f"/api/ml/datasets/{dataset_id}/examples")
            assert examples.status_code==200,examples.text
            rows=examples.json()["items"]
            assert all(not row["approved"] for row in rows)
            stats=client.get(f"/api/ml/datasets/{dataset_id}/stats")
            assert stats.json()["approved"]==0
            review=client.put(f"/api/ml/datasets/{dataset_id}/examples/{rows[0]['id']}",
                              headers=headers,json={"labels":["CONFIDENTIAL"],"approved":True})
            assert review.status_code==200,review.text
            assert client.get(f"/api/ml/datasets/{dataset_id}/stats").json()["approved"]==1
            bad=client.put(f"/api/ml/datasets/{dataset_id}/examples/{rows[0]['id']}",
                           headers=headers,json={"labels":["CONFIDENTIAL","NORMAL"],"approved":True})
            assert bad.status_code==422
        finally:
            with transaction() as session:
                session.execute(delete(TrainingExample).where(TrainingExample.dataset_id==dataset_id))
                session.execute(delete(MLDataset).where(MLDataset.id==dataset_id))
