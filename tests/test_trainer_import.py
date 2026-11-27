"""Exercise the server command using in-memory Django/ORM doubles, no server install."""
import importlib.util
import json
import sys
from contextlib import nullcontext
from importlib.metadata import version
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def importer(monkeypatch):
    def module(name, **attrs):
        value = ModuleType(name)
        value.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, value)

    class CommandError(Exception):
        pass

    module("django")
    module("django.core")
    module("django.core.management")
    module("django.core.management.base", BaseCommand=object, CommandError=CommandError)
    module("django.db", transaction=SimpleNamespace(atomic=nullcontext))
    categories = Mock()
    categories.objects.filter.return_value.values_list.return_value = ["custom-a", "custom-b"]
    models = Mock()
    models.objects.create.return_value.pk = "new-inactive"
    module("records.models", Category=categories, MLModel=models)
    service_path = Path(__file__).resolve().parents[1] / "records/trainer_import.py"
    service_spec = importlib.util.spec_from_file_location("records.trainer_import", service_path)
    service = importlib.util.module_from_spec(service_spec)
    monkeypatch.setitem(sys.modules, "records.trainer_import", service)
    service_spec.loader.exec_module(service)
    service.infer_models = Mock(return_value=([{"category": "custom-a", "threshold": .5},
                                              {"category": "custom-b", "threshold": .5}], []))
    path = Path(__file__).resolve().parents[1] / "records/management/commands/import_trainer_model.py"
    spec = importlib.util.spec_from_file_location("trainer_import_command", path)
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    command = imported.Command()
    command.stdout = Mock()
    return command, models, CommandError


def export(tmp_path):
    import hashlib

    artifact = b"fixture-not-deserialized"
    metrics = {"labels": ["custom-a", "custom-b"], "thresholds": [.5, .5]}
    eligible = False
    (tmp_path / "model.pkl").write_bytes(artifact)
    meta = dict(engine="tfidf", category_id=None, artifact="model.pkl",
                artifact_sha256=hashlib.sha256(artifact).hexdigest(), metrics=metrics,
                eligible=eligible, versions={p: version(p) for p in ("scikit-learn", "numpy")})
    (tmp_path / "training.json").write_text(json.dumps(meta))
    return dict(folder=tmp_path, name="Test", commit=False, trust_local_artifact=True)


def test_dry_run_never_writes_and_commit_never_activates(importer, tmp_path):
    command, models, _ = importer
    options = export(tmp_path)
    command.handle(**options)
    models.objects.create.assert_not_called()
    command.handle(**dict(options, commit=True))
    assert models.objects.create.call_args.kwargs["active"] is False
    assert models.objects.create.call_args.kwargs["category_id"] is None


def test_corrupt_import_never_writes(importer, tmp_path):
    command, models, error = importer
    options = export(tmp_path)
    (tmp_path / "model.pkl").write_bytes(b"broken")
    with pytest.raises(error, match="digest mismatch"):
        command.handle(**dict(options, commit=True))
    models.objects.create.assert_not_called()