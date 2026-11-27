"""Standalone contract tests; deliberately no Django or database imports."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ml import group_hash, infer, train
from app.ml_split import partition

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mice_trainer", ROOT / "tools/mice-trainer/trainer.py")
trainer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trainer)


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "smoke.jsonl"
    trainer.smoke_data(SimpleNamespace(output=path))
    return path


def test_arbitrary_labels_and_multilabel(tmp_path):
    path = tmp_path / "custom.jsonl"
    path.write_text(json.dumps(dict(id="a", group_id="g", labels=["custom-one", "custom-two"], text="hello")))
    assert trainer.read_rows(path)[0]["labels"] == ["custom-one", "custom-two"]


@pytest.mark.parametrize("changes, message", [
    ({"text": "same"}, "duplicate normalized"),
    ({"text": "SAME", "labels": ["different"]}, "duplicate normalized"),
    ({"id": "a", "text": "other"}, "duplicate id"),
    ({"group_id": ""}, "group_id"),
    ({"labels": ["x", "x"]}, "labels"),
])
def test_invalid_rows(tmp_path, changes, message):
    first = dict(id="a", group_id="g", text="same", labels=["x"])
    second = dict(first, id="b", **{})
    second.update(changes)
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in (first, second)))
    with pytest.raises(ValueError, match=message):
        trainer.read_rows(path)


def test_seed_grouped_split_and_no_leakage(corpus):
    rows = trainer.read_rows(corpus)
    groups = {group_hash(r["text"]): {k: v for k, v in r.items() if k != "split"} for r in rows}
    one = partition(groups, seed=17)
    assert one == partition(dict(reversed(list(groups.items()))), seed=17)
    assert one != partition(groups, seed=18)
    semantic = [{groups[k]["group_id"] for k in keys} for keys in one.values()]
    assert all(not a & b for i, a in enumerate(semantic) for b in semantic[i + 1:])
    trainer.prepare(list(groups.values()), seed=17)


def test_tfidf_export_reproducibility_and_cpu_runtime(corpus, tmp_path):
    rows = trainer.read_rows(corpus)
    one, metrics, eligible = train(rows, seed=19)
    two, again, _ = train(rows, seed=19)
    assert one == two and metrics == again
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "model.pkl").write_bytes(one)
    split = [dict(text_sha256=group_hash(r["text"]), group_id=r["group_id"]) for r in rows]
    trainer.dump(folder / "split.json", split)
    trainer.dump(folder / "training.json", dict(engine="tfidf", category_id=None,
        artifact="model.pkl", artifact_sha256=trainer.sha(one), metrics=metrics,
        split_sha256=trainer.sha((folder / "split.json").read_bytes()), eligible=eligible))
    model, _ = trainer.load_model(folder)
    predictions, errors = trainer.infer_models([model], rows[0]["text"])
    assert not errors and predictions == [dict(p, model_id=1, engine="tfidf") for p in infer(one, rows[0]["text"])]
    with pytest.raises(ValueError, match="already seen"):
        trainer.evaluate(SimpleNamespace(model=folder, dataset=corpus, output=None))
    (folder / "model.pkl").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        trainer.load_model(folder)


def test_neural_rejects_invalid_device_and_quality_gate():
    from app.ml_engines import train_binary

    with pytest.raises(ValueError, match="device"):
        train_binary([], "setfit", "custom", .7, device="bogus")
    with pytest.raises(ValueError, match="F1"):
        train_binary([], "rubert", "custom", 2)


def test_device_environment_restored_after_failure(monkeypatch):
    from app.ml_engines import _training_device

    monkeypatch.setenv("ACCELERATE_USE_CPU", "original")
    with pytest.raises(RuntimeError):
        with _training_device("cpu"):
            import os

            assert os.environ["ACCELERATE_USE_CPU"] == "true"
            raise RuntimeError("training failed")
    import os

    assert os.environ["ACCELERATE_USE_CPU"] == "original"