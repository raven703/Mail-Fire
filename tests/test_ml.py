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


def test_preassigned_grouped_training_keeps_semantic_groups_separate():
    data = []
    for split in ("train", "validation", "test"):
        for label in ("finance", "public"):
            for group in range(5):
                data += [
                    {"text": f"{label} scenario {split} {group} variant {variant}",
                     "labels": [label], "group_id": f"{split}:{label}:{group}", "split": split}
                    for variant in range(2)
                ]
    _, metrics, _ = train(data, min_f1=0)
    hashes = metrics["split_group_hashes"]
    lookup = {group_hash(row["text"]): row["group_id"] for row in data}
    groups = [{lookup[key] for key in values} for values in hashes.values()]
    assert all(not one & two for i, one in enumerate(groups) for two in groups[i + 1:])
    with pytest.raises(ValueError, match="crosses splits"):
        train(data + [{**data[0], "text": "different text", "split": "test"}])


def test_grouped_training_rejects_missing_class_or_conflicting_duplicate():
    data = examples()
    for row in data:
        row["group_id"] = row["labels"][0] + ":" + row["text"].split()[-1]
    _, metrics, _ = train(data, min_f1=0)
    assert sum(metrics["split_sizes"].values()) == len(data)
    with pytest.raises(ValueError, match="conflicting group or split"):
        train(data + [{**data[0], "group_id": "another"}])
    for row in data:
        row["split"] = "train" if "finance" in row["labels"] else "validation"
    with pytest.raises(ValueError, match="Every split needs examples"):
        train(data)
