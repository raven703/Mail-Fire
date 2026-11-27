"""Infrastructure only: never train, download weights, or touch the server DB."""
import importlib.util
import io
import json
import sys
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trainer_package import digest, inspect_package, versions, write_package

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trainer_infra", ROOT / "tools/mice-trainer/trainer.py")
trainer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trainer)


def metadata():
    return dict(engine="tfidf", category_id=None, categories=["a", "b"],
                metrics={"labels": ["a", "b"], "thresholds": [.4, .6]},
                thresholds=[.4, .6], eligible=False, versions=versions())


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "models.zip"
    write_package(path, [(metadata(), b"fixture-not-pickle"), (metadata(), b"second")], {"status": "completed"})
    return path


def test_package_roundtrip(package):
    manifest = inspect_package(package)
    assert len(manifest["models"]) == 2
    with zipfile.ZipFile(package) as archive:
        assert set(archive.namelist()) == {"manifest.json", "report.json", "models/m1/model.pkl", "models/m2/model.pkl"}


@pytest.mark.parametrize("attack", ["hash", "path", "extra", "format", "threshold", "duplicate", "report"])
def test_reject_corruption(package, tmp_path, attack):
    with zipfile.ZipFile(package) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    if attack == "hash":
        files["models/m1/model.pkl"] = b"corrupt"
    elif attack == "path":
        files["../escape"] = b"bad"
    elif attack == "extra":
        files["emails.jsonl"] = b"bad"
    elif attack == "format":
        manifest["format"] = 999
    elif attack == "threshold":
        manifest["models"][0]["metrics"]["thresholds"] = [2, .5]
    elif attack == "report":
        files["report.json"] = b"{}"
    files["manifest.json"] = json.dumps(manifest).encode()
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        if attack == "duplicate":
            with pytest.warns(UserWarning):
                archive.writestr("report.json", b"{}")
    with pytest.raises(ValueError):
        inspect_package(bad)


def test_broken_zip():
    with pytest.raises(ValueError):
        inspect_package(io.BytesIO(b"broken"))


@pytest.fixture
def job(tmp_path):
    # Dataset reader is mocked: no dataset generation and no classifier calls.
    value = dict(name="test", dataset="existing.jsonl", categories=["a", "b"],
                 engines=["tfidf", "setfit", "rubert"], device="cpu", epochs=2,
                 batch_size=8, max_steps=5, seed=42, min_f1=.7, output="results")
    path = tmp_path / "job.json"
    path.write_text(json.dumps(value))
    return path


def mock_rows(monkeypatch):
    rows = [dict(id=str(i), group_id=str(i // 2), text=f"fixture {i}", labels=["a", "b"] if i % 2 else [],
                 split=("train", "validation", "test")[i // 10]) for i in range(30)]
    monkeypatch.setattr(trainer, "read_rows", Mock(return_value=rows))
    return rows


def test_dry_run(job, monkeypatch):
    mock_rows(monkeypatch)
    training = Mock(side_effect=AssertionError("must not train"))
    monkeypatch.setattr(trainer, "training", training)
    plan = trainer.run_job(SimpleNamespace(job=job, dry_run=True))
    assert plan["model_count"] == 5
    assert not (job.parent / "results").exists()
    training.assert_not_called()


@pytest.mark.parametrize("key,value", [("epochs", True), ("seed", -1), ("engines", ["bogus"]),
    ("categories", ["a"]), ("device", "gpu"), ("min_f1", 2), ("batch_size", 0), ("max_steps", 0)])
def test_invalid_job(job, monkeypatch, key, value):
    mock_rows(monkeypatch)
    data = json.loads(job.read_text())
    data[key] = value
    job.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        trainer.read_job(job)


def test_orchestration_mock_training(job, monkeypatch):
    mock_rows(monkeypatch)
    data = json.loads(job.read_text())
    data["engines"] = ["tfidf"]
    job.write_text(json.dumps(data))

    def fake_training(args):
        args.output.mkdir()
        (args.output / "model.pkl").write_bytes(b"fixture")
        meta = dict(metadata(), artifact="model.pkl")
        trainer.dump(args.output / "training.json", meta)

    train_mock = Mock(side_effect=fake_training)
    monkeypatch.setattr(trainer, "training", train_mock)
    trainer.run_job(SimpleNamespace(job=job, dry_run=False))
    train_mock.assert_called_once()
    assert inspect_package(job.parent / "results/models.zip")["models"][0]["eligible"] is False
    assert not (job.parent / "results/.job-input.jsonl").exists()


@pytest.fixture
def service(monkeypatch):
    models = ModuleType("records.models")
    models.Category = Mock()
    models.Category.objects.filter.return_value.values_list.return_value = ["a", "b"]
    models.MLModel = Mock()
    monkeypatch.setitem(sys.modules, "records.models", models)
    spec = importlib.util.spec_from_file_location("isolated_trainer_service", ROOT / "records/trainer_import.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.transaction, "atomic", nullcontext)
    module.infer_models = Mock(return_value=([{"category": "a", "threshold": .4},
                                             {"category": "b", "threshold": .6}], []))
    return module, models


def test_trust_preview_selection_inactive_no_training(service, package):
    module, models = service
    module.preview(package)
    module.infer_models.assert_not_called()
    with pytest.raises(ValueError, match="trust"):
        module.import_models(package, commit=True)
    module.infer_models.assert_not_called()
    module.import_models(package, ["m2"], trusted=True, commit=False)
    models.MLModel.objects.create.assert_not_called()
    module.import_models(package, ["m2"], trusted=True, commit=True)
    call = models.MLModel.objects.create.call_args.kwargs
    assert call["active"] is False and call["artifact"] == b"second"
    models.MLModel.objects.create.assert_called_once()


def test_version_and_category_rejection(service, package):
    module, models = service
    models.Category.objects.filter.return_value.values_list.return_value = []
    with pytest.raises(ValueError, match="categories"):
        module.preview(package)
    models.MLModel.objects.create.assert_not_called()
    from app.trainer_package import check_versions
    meta = metadata()
    meta["versions"] = {"scikit-learn": "wrong"}
    with pytest.raises(ValueError, match="version"):
        check_versions(meta)


def test_web_admin_preview_import(service, monkeypatch, package):
    module, models = service
    operations = ModuleType("records.operations")
    from django.http import HttpResponseForbidden
    operations.admin_access = lambda request: None if request.user.admin else HttpResponseForbidden()
    monkeypatch.setitem(sys.modules, "records.operations", operations)
    monkeypatch.setitem(sys.modules, "records.trainer_import", module)
    from django.conf import settings
    if not settings.configured:
        settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="isolated-test", DATABASES={})
    spec = importlib.util.spec_from_file_location("isolated_trainer_view", ROOT / "records/trainer_views.py")
    view = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(view)
    view.render = Mock(side_effect=lambda *args, **kwargs: (args, kwargs))
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.http import QueryDict
    request = SimpleNamespace(method="POST", user=SimpleNamespace(admin=False), session={}, headers={},
                              POST=QueryDict(""), FILES={})
    assert view.trainer_import(request).status_code == 403
    request.user.admin = True
    request.FILES = {"package": SimpleUploadedFile("models.zip", package.read_bytes())}
    result = view.trainer_import(request)
    assert result[0][2]["manifest"]["format"] == 1
    module.infer_models.assert_not_called()
    assert request.session["trainer_preview"] == digest(package.read_bytes())
    request.POST = QueryDict("action=import&trust=yes&models=m1")
    request.FILES = {"package": SimpleUploadedFile("models.zip", package.read_bytes())}
    view.trainer_import(request)
    assert models.MLModel.objects.create.call_args.kwargs["active"] is False


def test_legacy_cli_no_training(service, monkeypatch, tmp_path):
    module, models = service
    monkeypatch.setitem(sys.modules, "records.trainer_import", module)
    meta = metadata()
    raw = b"legacy-fixture"
    meta.update(artifact="model.pkl", artifact_sha256=digest(raw))
    (tmp_path / "model.pkl").write_bytes(raw)
    (tmp_path / "training.json").write_text(json.dumps(meta))
    spec = importlib.util.spec_from_file_location("isolated_import_command",
        ROOT / "records/management/commands/import_trainer_model.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    command = cli.Command()
    command.stdout = Mock()
    options = dict(folder=tmp_path, trust_local_artifact=True, name="legacy", commit=False)
    command.handle(**options)
    models.MLModel.objects.create.assert_not_called()
    command.handle(**dict(options, commit=True))
    assert models.MLModel.objects.create.call_args.kwargs["active"] is False


def test_neural_single_package(tmp_path):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("model/fixture", b"fixture")
    meta = dict(engine="rubert", category_id="custom", categories=["custom"],
                metrics={"labels": ["custom"], "threshold": .5}, thresholds=[.5], eligible=True,
                versions={"torch": "fixture"})
    path = tmp_path / "single.zip"
    write_package(path, [(meta, raw.getvalue())], {})
    assert len(inspect_package(path)["models"]) == 1


def test_training_failure_report_cleanup(job, monkeypatch):
    mock_rows(monkeypatch)
    monkeypatch.setattr(trainer, "training", Mock(side_effect=RuntimeError("mock failure")))
    with pytest.raises(RuntimeError, match="mock failure"):
        trainer.run_job(SimpleNamespace(job=job, dry_run=False))
    output = job.parent / "results"
    assert json.loads((output / "report.json").read_text())["status"] == "failed"
    assert not (output / "models.zip").exists()
    assert not (output / ".job-input.jsonl").exists()


def test_django_templates_render():
    from django.template import Context, Engine
    # Real template parsing/rendering without a project URLconf, ORM or DB.
    engine = Engine(dirs=[str(ROOT / "templates")])
    for name in ("records/trainer_import.html", "records/trainer_import_content.html", "records/ml_base.html"):
        engine.get_template(name)
    source = (ROOT / "templates/records/trainer_import_content.html").read_text()
    source = source.replace("{% url 'trainer-import' %}", "/models/import/")
    rendered = engine.from_string(source).render(Context({"manifest": {"models": [dict(metadata(), id="m1")]}}))
    assert "m1" in rendered and "tfidf" in rendered and 'name="trust"' in rendered
    assert "hx-post" in rendered and "csrfmiddlewaretoken" not in rendered  # no request token in isolated Context


def test_oversized_zip(package, monkeypatch):
    import app.trainer_package as packages
    monkeypatch.setattr(packages, "MAX_FILE", 2)
    with pytest.raises(ValueError, match="large"):
        inspect_package(package)


def test_all_engines_same_split_and_independent_evaluation(job, monkeypatch):
    rows = mock_rows(monkeypatch)
    data = json.loads(job.read_text())
    data["evaluation_dataset"] = "independent.jsonl"
    job.write_text(json.dumps(data))
    external = [dict(id="external1", group_id="external", text="external positive", labels=["a", "b"]),
                dict(id="external2", group_id="external", text="external negative", labels=[])]
    monkeypatch.setattr(trainer, "read_rows", Mock(side_effect=[rows, external]))
    seen = []

    def fake_training(args):
        seen.append([r["split"] for r in map(json.loads, args.dataset.read_text().splitlines())])
        args.output.mkdir()
        meta = metadata()
        if args.engine == "tfidf":
            raw, filename = b"fixture", "model.pkl"
        else:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("manifest.json", "{}")
            raw, filename = stream.getvalue(), "model.zip"
            meta.update(engine=args.engine, category_id=args.category,
                        metrics={"labels": [args.category], "threshold": .5})
        (args.output / filename).write_bytes(raw)
        trainer.dump(args.output / "training.json", dict(meta, artifact=filename))

    monkeypatch.setattr(trainer, "training", fake_training)
    evaluation = Mock(side_effect=lambda args: trainer.dump(args.output, {"fixture": True}))
    monkeypatch.setattr(trainer, "evaluate", evaluation)
    trainer.run_job(SimpleNamespace(job=job, dry_run=False))
    assert len(seen) == 5 and all(split == seen[0] for split in seen)
    assert evaluation.call_count == 5
    assert len(inspect_package(job.parent / "results/models.zip")["models"]) == 5


def test_import_validation_failure_never_writes(service, package):
    module, models = service
    module.infer_models.return_value = ([], [{"error": "fixture"}])
    with pytest.raises(ValueError, match="inference"):
        module.import_models(package, trusted=True, commit=True)
    models.MLModel.objects.create.assert_not_called()
    module.infer_models.return_value = ([{"category": "a", "threshold": .1},
                                        {"category": "b", "threshold": .6}], [])
    with pytest.raises(ValueError, match="thresholds"):
        module.import_models(package, trusted=True, commit=True)
    models.MLModel.objects.create.assert_not_called()
    with pytest.raises(ValueError, match="Select"):
        module.import_models(package, ["nonexistent"], trusted=True, commit=True)


def test_evaluation_overlap_rejected(job, monkeypatch):
    rows = mock_rows(monkeypatch)
    data = json.loads(job.read_text())
    data["evaluation_dataset"] = "overlap.jsonl"
    job.write_text(json.dumps(data))
    monkeypatch.setattr(trainer, "read_rows", Mock(side_effect=[rows, rows]))
    with pytest.raises(ValueError, match="overlap"):
        trainer.read_job(job)


def test_zip_symlink_rejected(tmp_path):
    path = tmp_path / "symlink.zip"
    entry = zipfile.ZipInfo("link")
    entry.create_system = 3
    entry.external_attr = 0o120777 << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(entry, "target")
    with pytest.raises(ValueError, match="Unsafe"):
        inspect_package(path)