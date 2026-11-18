import pytest

from app.ml import group_hash, infer, train


def examples():
    return [
        {
            "text": f"Секретный финансовый бюджет confidential finance forecast revenue costs номер {i}",
            "labels": ["finance"],
        }
        for i in range(100)
    ] + [
        {
            "text": f"Публичное приглашение public invitation picnic party meeting greetings номер {i}",
            "labels": ["public"],
        }
        for i in range(100)
    ]


def test_real_training_and_inference():
    artifact, metrics, eligible = train(examples())
    assert eligible
    sets = [set(v) for v in metrics["split_group_hashes"].values()]
    assert all(not a & b for i, a in enumerate(sets) for b in sets[i + 1 :])
    predictions = infer(artifact, "Секретный финансовый бюджет confidential finance forecast revenue")
    assert next(p for p in predictions if p["category"] == "finance")["matched"]
    assert metrics["test"]["finance"]["f1"] >= 0.7


def test_untrained_and_conflicting_labels():
    with pytest.raises(ValueError):
        train([])
    with pytest.raises(ValueError, match="Conflicting"):
        train([{"text": "same text", "labels": ["a"]}, {"text": "SAME   TEXT", "labels": ["b"]}])
    assert group_hash("SAME   TEXT") == group_hash("same text")
