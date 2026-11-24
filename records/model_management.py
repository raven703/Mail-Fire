"""Native model lifecycle; publication does not enable detection inference."""

import hashlib
import re
from uuid import uuid4

from django import forms
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from pipeline.models import WorkItem
from pipeline.services import enqueue, finish, locked_current
from records.models import Audit, Category, MLDataset, MLModel, TrainingExample
from records.operations import admin_access
from records.workspace import access


def snapshot_hash(rows):
    value = "\n".join(sorted(
        hashlib.sha256(re.sub(r"\s+", " ", row["text"]).strip().lower().encode()).hexdigest()
        + ":" + ",".join(sorted(row["labels"])) for row in rows
    ))
    return hashlib.sha256(value.encode()).hexdigest()


class TrainingForm(forms.Form):
    name = forms.CharField(max_length=100)
    dataset = forms.ModelChoiceField(queryset=MLDataset.objects.none(), required=False)
    engine = forms.ChoiceField(choices=[("tfidf", "TF-IDF"), ("setfit", "SetFit"), ("rubert", "RuBERT")])
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    min_f1 = forms.FloatField(min_value=0.5, max_value=1, initial=0.7)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MLDataset.objects.order_by("name")
        self.fields["category"].queryset = Category.objects.filter(active=True).exclude(mode="label").order_by("name")

    def clean(self):
        values = super().clean()
        if values.get("engine") == "tfidf" and values.get("category"):
            self.add_error("category", "TF-IDF — общая многометочная модель")
        if values.get("engine") in {"setfit", "rubert"} and not values.get("category"):
            self.add_error("category", "Выберите категорию")
        return values


def corpus(dataset_id):
    rows = TrainingExample.objects.filter(approved=True)
    if dataset_id:
        rows = rows.filter(dataset_id=dataset_id)
    result = list(rows.order_by("pk").values("text", "labels")[:10001])
    if not 30 <= len(result) <= 10000:
        raise ValueError("Нужно 30–10000 утверждённых примеров")
    return result


def train_job(job):
    # Heavy libraries are loaded only by the dedicated training worker.
    rows = corpus(job.payload.get("dataset_id"))
    snapshot = snapshot_hash(rows)
    if snapshot != job.payload["snapshot_sha"]:
        raise ValueError("Training corpus changed; queue a new training job")
    engine = job.payload["engine"]
    if engine == "tfidf":
        from app.ml import train

        artifact, metrics, eligible = train(rows, job.payload["min_f1"])
    else:
        from app.ml_engines import train_binary

        artifact, metrics, eligible = train_binary(rows, engine, job.payload["category_id"], job.payload["min_f1"])
    metrics = {**metrics, "dataset_snapshot_sha": snapshot, "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
               "dataset_id": job.payload.get("dataset_id"), "training_job": str(job.pk)}
    with transaction.atomic():
        locked_current(job.pk, job.token)
        model = MLModel.objects.create(
            name=job.payload["name"], engine=engine, category_id=job.payload.get("category_id"),
            dataset_id=job.payload.get("dataset_id"), artifact=artifact, metrics=metrics, eligible=eligible, active=False,
        )
        Audit.objects.create(actor="training", action="model_trained", target=model.pk,
                             details={"job": str(job.pk), "snapshot": snapshot, "eligible": eligible})
        finish(job.pk, job.token, {"model_id": model.pk, "eligible": eligible})


@transaction.atomic
def model_action(actor, model_id, action):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('ml-publication'))")
    row = get_object_or_404(MLModel.objects.select_for_update(), pk=model_id)
    before = list(MLModel.objects.filter(category_id=row.category_id, active=True).values_list("pk", flat=True))
    if action in {"publish", "rollback"}:
        if not row.eligible:
            raise ValueError("Модель не прошла quality gate")
        MLModel.objects.filter(category_id=row.category_id).update(active=False)
        row.active = True
        row.save(update_fields=["active"])
    elif action == "deactivate":
        row.active = False
        row.save(update_fields=["active"])
    elif action == "delete":
        if row.active:
            raise ValueError("Активную модель удалить нельзя")
        row.delete()
    else:
        raise ValueError("Неизвестное действие")
    Audit.objects.create(actor=actor.pk, action="model_" + action, target=model_id,
                         details={"previous_active": before, "inference_enabled": False})


@require_http_methods(["GET", "POST"])
def models(request):
    error = admin_access(request)
    if error is not None:
        return error
    error = access(request, originals=True)
    if error is not None:
        return error
    form = TrainingForm(request.POST if request.method == "POST" and request.POST.get("action") == "train" else None)
    message = ""
    if request.method == "POST":
        try:
            if request.POST.get("action") == "train" and form.is_valid():
                values = form.cleaned_data
                dataset_id = values["dataset"].pk if values["dataset"] else None
                rows = corpus(dataset_id)
                with transaction.atomic():
                    job = enqueue("training.model", {
                        "name": values["name"], "engine": values["engine"], "dataset_id": dataset_id,
                        "category_id": values["category"].pk if values["category"] else None,
                        "min_f1": values["min_f1"], "snapshot_sha": snapshot_hash(rows),
                    }, "training:" + uuid4().hex)
                    Audit.objects.create(actor=request.user.pk, action="model_training_requested", target=str(job.pk))
                return redirect("models-page")
            elif request.POST.get("action") != "train":
                model_action(request.user, request.POST.get("model_id"), request.POST.get("action"))
                return redirect("models-page")
        except ValueError as exc:
            message = str(exc)
    return render(request, "records/models.html", {
        "form": form, "error": message,
        "models": MLModel.objects.defer("artifact").order_by("-created_at")[:100],
        "jobs": WorkItem.objects.filter(kind="training.model").order_by("-created_at")[:30],
    }, status=400 if message or form.is_bound else 200)