"""Untrusted external labels and optional local binary classifiers."""
import csv
import io
import json
from types import SimpleNamespace

import pytest

from app.datasets import parse_dataset
from app.ml_engines import _binary_data


def test_jsonl_maps_external_llm_labels_without_approving_them():
    rows = [
        {"text":"Тестовый финансовый прогноз выручки следующего года", "labels":["finance"]},
        {"text":"Обычная общественная информация для корпоративного сайта", "labels":[]},
        {"text":"Тестовый финансовый прогноз выручки следующего года", "labels":["finance"]},
    ]
    blob="\n".join(json.dumps(row,ensure_ascii=False) for row in rows).encode()
    parsed=parse_dataset(blob,"synthetic.jsonl",{"finance":"custom-finance","NORMAL":"NORMAL"})
    assert len(parsed)==2
    assert parsed[0]["labels"]==["custom-finance"]
    assert parsed[1]["labels"]==["NORMAL"]


def test_csv_and_invalid_imports():
    data=io.StringIO()
    writer=csv.DictWriter(data,fieldnames=["text","labels"])
    writer.writeheader()
    writer.writerow({"text":"Длинный текст о финансовом прогнозе будущего года","labels":"fin;secret"})
    labels={"fin":"CUSTOM_FIN","secret":"SECRET","NORMAL":"NORMAL"}
    parsed=parse_dataset(data.getvalue().encode(),"synthetic.csv",labels)
    assert parsed[0]["labels"]==["CUSTOM_FIN","SECRET"]
    with pytest.raises(ValueError,match="неизвестные метки"):
        parse_dataset(b'{"text":"Synthetic document longer than ten","labels":["UNKNOWN"]}',"test.jsonl",labels)
    with pytest.raises(ValueError,match="NORMAL"):
        parse_dataset(b'{"text":"Synthetic document longer than ten","labels":["NORMAL","fin"]}',"test.jsonl",labels)
    with pytest.raises(ValueError,match="UTF-8"):
        parse_dataset(b"\xff\xfe","test.csv",labels)
    with pytest.raises(ValueError,match="Допустимы"):
        parse_dataset(b"arbitrary","test.exe",labels)


def test_external_duplicate_conflict_and_size_limits():
    rows=[
        {"text":"Synthetic confidential information example","labels":["fin"]},
        {"text":"Synthetic CONFIDENTIAL information example","labels":[]},
    ]
    blob="\n".join(json.dumps(row) for row in rows).encode()
    with pytest.raises(ValueError,match="противоречивая"):
        parse_dataset(blob,"test.jsonl",{"fin":"CUSTOM_FIN"})
    large=json.dumps({"text":"a"*100001,"labels":[]}).encode()
    with pytest.raises(ValueError,match="100000"):
        parse_dataset(large,"test.jsonl",{})


def test_binary_splits_are_stratified_without_leakage():
    from app.ml import group_hash

    data=[{"text":f"Публичная информация о природе и путешествиях вариант {i}", "labels":["NORMAL"]}
          for i in range(35)]
    data += [{"text":f"Внутренний финансовый прогноз бюджета и выручки вариант {i}", "labels":["FINANCE"]}
             for i in range(35)]
    splits=_binary_data(data,"FINANCE")
    hashes=[{group_hash(text) for text in texts} for texts,_ in splits.values()]
    assert all(not one & two for i,one in enumerate(hashes) for two in hashes[i+1:])
    assert all(set(targets)=={0,1} for _,targets in splits.values())
    with pytest.raises(ValueError,match="минимум 6"):
        _binary_data(data[:65],"FINANCE")


def test_model_runtime_preference_and_failure_isolation(monkeypatch):
    from app import ml_runtime

    rows=[
        SimpleNamespace(id="global",engine="tfidf",category_id=None,artifact=b"tfidf",metrics={}),
        SimpleNamespace(id="special",engine="setfit",category_id="FINANCE",artifact=b"setfit",metrics={"threshold":.7}),
        SimpleNamespace(id="bad",engine="rubert",category_id="SECRET",artifact=b"bad",metrics={"threshold":.6}),
    ]
    class Session:
        def scalars(self,_query):
            return iter(rows)
    monkeypatch.setattr("app.ml.infer",lambda artifact,text:[
        {"category":"FINANCE","matched":False,"confidence":.2},
        {"category":"SECRET","matched":True,"confidence":.8},
    ])
    def local(artifact,text,category,threshold):
        if category=="SECRET":
            raise RuntimeError("not available")
        return {"category":category,"matched":True,"confidence":.94}
    monkeypatch.setattr("app.ml_engines.infer_binary",local)
    predictions,errors=ml_runtime.infer_active(Session(),"synthetic")
    assert next(p for p in predictions if p["category"]=="FINANCE")["confidence"]==.94
    assert next(p for p in predictions if p["category"]=="SECRET")["engine"]=="tfidf"
    assert len(errors)==1 and errors[0]["model_id"]=="bad"
