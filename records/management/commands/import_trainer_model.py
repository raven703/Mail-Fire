"""Explicit trusted local import; never activates models or changes existing rows."""
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.ml_runtime import infer_models
from records.models import Category, MLModel


class Command(BaseCommand):
    help = "Validate a trusted Trainer export on CPU; import inactive only with --commit"

    def add_arguments(self, parser):
        parser.add_argument("folder", type=Path)
        parser.add_argument("--trust-local-artifact", action="store_true", required=True)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--name", default="MICE Trainer import")

    def handle(self, *args, **options):
        folder = options["folder"].expanduser().resolve()
        try:
            meta = json.loads((folder / "training.json").read_text())
            engine = meta["engine"]
            if engine not in {"tfidf", "setfit", "rubert"}:
                raise ValueError("Unknown engine")
            filename = "model.pkl" if engine == "tfidf" else "model.zip"
            if meta["artifact"] != filename:
                raise ValueError("Invalid artifact filename")
            artifact = (folder / filename).read_bytes()
            if hashlib.sha256(artifact).hexdigest() != meta["artifact_sha256"]:
                raise ValueError("Artifact digest mismatch")
            if meta["versions"]["scikit-learn"] != version("scikit-learn"):
                raise ValueError("scikit-learn version mismatch; use the native dependency locks")
            category = meta["category_id"]
            if (engine == "tfidf" and category is not None) or (engine != "tfidf" and not category):
                raise ValueError("Invalid category metadata")
            model = SimpleNamespace(id="import-check", engine=engine, category_id=category,
                                    artifact=artifact, metrics=meta["metrics"])
            predictions, errors = infer_models([model], "Проверка импорта обученной модели")
            if errors or not predictions:
                raise ValueError(f"CPU inference failed: {errors}")
            labels = set(meta["metrics"]["labels"])
            if {p["category"] for p in predictions} != labels:
                raise ValueError("Artifact labels differ from metadata")
            missing = labels - set(Category.objects.filter(pk__in=labels).values_list("pk", flat=True))
            if missing:
                raise ValueError(f"Create categories first: {sorted(missing)}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc
        if not options["commit"]:
            self.stdout.write("Validated on CPU; dry run, no database writes")
            return
        with transaction.atomic():
            imported = MLModel.objects.create(engine=engine, category_id=category,
                                             name=options["name"], artifact=artifact,
                                             metrics=meta["metrics"], eligible=bool(meta["eligible"]),
                                             active=False)
        self.stdout.write(f"Imported inactive model {imported.pk}; publication remains manual")