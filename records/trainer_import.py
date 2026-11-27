"""Shared trusted import service; no training or activation paths."""
import hashlib
import json
import zipfile
from types import SimpleNamespace

from django.db import transaction

from app.ml_runtime import infer_models
from app.trainer_package import MAX_FILE, MAX_MANIFEST, check_versions, inspect_package, validate_model
from records.models import Category, MLModel


def check_categories(meta):
    labels = set(meta["categories"])
    missing = labels - set(Category.objects.filter(pk__in=labels).values_list("pk", flat=True))
    if missing:
        raise ValueError(f"Create categories first: {sorted(missing)}")
    check_versions(meta)


def preview(source):
    manifest = inspect_package(source)
    for meta in manifest["models"]:
        check_categories(meta)
    return manifest


def import_models(source, selected=None, *, trusted=False, commit=False, name="MICE Trainer import"):
    if not trusted:
        raise ValueError("Explicit trust confirmation is required before deserialization")
    if hasattr(source, "is_dir") and source.is_dir():
        if (source / "training.json").stat().st_size > MAX_MANIFEST:
            raise ValueError("Metadata too large")
        meta = json.loads((source / "training.json").read_text())
        if meta.get("format", 1) != 1:
            raise ValueError("Unsupported model format")
        filename = "model.pkl" if meta["engine"] == "tfidf" else "model.zip"
        if meta["artifact"] != filename:
            raise ValueError("Invalid artifact filename")
        if (source / filename).stat().st_size > MAX_FILE:
            raise ValueError("Artifact too large")
        raw = (source / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["artifact_sha256"]:
            raise ValueError("Artifact digest mismatch")
        meta.update(categories=meta["metrics"]["labels"],
                    thresholds=meta["metrics"].get("thresholds", [meta["metrics"].get("threshold")]))
        validate_model(meta)
        check_categories(meta)
        entries = [(meta, raw)]
    else:
        manifest = preview(source)
        available = {m["id"] for m in manifest["models"]}
        selected = available if selected is None else set(selected)
        if not selected or selected - available:
            raise ValueError("Select valid models")
        if hasattr(source, "seek"):
            source.seek(0)
        with zipfile.ZipFile(source) as archive:
            entries = [(m, archive.read(m["artifact"])) for m in manifest["models"] if m["id"] in selected]
    for meta, raw in entries:
        model = SimpleNamespace(id="import-check", engine=meta["engine"], category_id=meta["category_id"],
                                artifact=raw, metrics=meta["metrics"])
        predictions, errors = infer_models([model], "Проверка импорта обученной модели")
        if errors or {p["category"] for p in predictions} != set(meta["categories"]):
            raise ValueError(f"CPU inference/labels check failed: {errors}")
        expected = dict(zip(meta["categories"], meta["thresholds"]))
        if any(p.get("threshold") != expected[p["category"]] for p in predictions):
            raise ValueError("Artifact thresholds differ from manifest")
    if not commit:
        return []
    with transaction.atomic():
        return [MLModel.objects.create(engine=meta["engine"], category_id=meta["category_id"],
                name=name, artifact=raw, metrics=meta["metrics"], eligible=meta["eligible"], active=False)
                for meta, raw in entries]