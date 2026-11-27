"""Native model lifecycle; publication does not enable detection inference."""

import hashlib
import re
from uuid import uuid4

from django import forms
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models.functions import Left
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from app.category_catalog import LEGACY_ALIASES
from pipeline.models import WorkItem
from pipeline.services import enqueue, finish, locked_current
from records.category_picker import LabelForm
from records.datasets import update_dataset
from records.ml_status import ml_status
from records.models import Audit, Category, MLDataset, MLModel, TrainingExample
from records.operations import admin_access
from records.workspace import access


def snapshot_hash(rows):
    value = "\n".join(sorted(
        hashlib.sha256(re.sub(r"\s+", " ", row["text"]).strip().lower().encode()).hexdigest()
        + ":" + ",".join(sorted(row["labels"])) for row in rows
    ))
    return hashlib.sha256(value.encode()).hexdigest()


class TrainingLabelForm(forms.Form):
    name = forms.CharField(max_length=160, min_length=2, label="Название метки")
    description = forms.CharField(max_length=2000, required=False, label="Описание",
                                  widget=forms.Textarea(attrs={"rows": 2}))

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Category.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("Название уже используется в каталоге категорий или меток")
        return name


class TrainingForm(forms.Form):
    name = forms.CharField(max_length=100, label="Название версии")
    dataset = forms.ModelChoiceField(queryset=MLDataset.objects.none(), required=False, label="Датасет",
                                     empty_label="Все подтверждённые примеры")
    engine = forms.ChoiceField(label="Движок обучения", choices=[
        ("tfidf", "TF-IDF — лёгкий классификатор"), ("setfit", "SetFit"), ("rubert", "RuBERT-tiny2"),
    ])
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False, label="Категория для модели",
                                      empty_label="Выберите категорию")
    min_f1 = forms.FloatField(min_value=0.5, max_value=1, initial=0.7, label="Минимальный F1",
                              widget=forms.NumberInput(attrs={"step": "0.01"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MLDataset.objects.order_by("name", "-version")
        self.fields["dataset"].label_from_instance = lambda row: f"{row.name} (v{row.version})"
        self.fields["category"].queryset = Category.objects.filter(active=True).exclude(mode="label").exclude(pk__in=LEGACY_ALIASES).order_by("name")
        self.fields["category"].label_from_instance = lambda row: row.name

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
    expected = "training.model" if job.payload["engine"] == "tfidf" else "training.neural"
    if job.kind != expected:
        raise ValueError("Training engine/queue mismatch")
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
        dataset_id = job.payload.get("dataset_id")
        dataset = MLDataset.objects.select_for_update().filter(pk=dataset_id).first() if dataset_id else None
        model = MLModel.objects.create(
            name=job.payload["name"], engine=engine, category_id=job.payload.get("category_id"),
            dataset=dataset, artifact=artifact, metrics=metrics, eligible=eligible, active=False,
        )
        Audit.objects.create(actor="training", action="model_trained", target=model.pk,
                             details={"job": str(job.pk), "snapshot": snapshot, "eligible": eligible})
        finish(job.pk, job.token, {"model_id": model.pk, "eligible": eligible})


@transaction.atomic
def model_action(actor, model_id, action):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('ml-publication'))")
    row = get_object_or_404(MLModel.objects.select_for_update(), pk=model_id)
    before = list(MLModel.objects.filter(category_id=row.category_id, engine=row.engine, active=True).values_list("pk", flat=True))
    if action in {"publish", "rollback"}:
        if not row.eligible:
            raise ValueError("Модель не прошла quality gate")
        MLModel.objects.filter(category_id=row.category_id, engine=row.engine).update(active=False)
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


class ManualExampleForm(LabelForm):
    text = forms.CharField(min_length=10, max_length=100000, label="Текст примера", widget=forms.Textarea)
    field_order = ("text", "labels", "approved")


@transaction.atomic
def add_example(actor, values):
    text = values["text"]
    digest = hashlib.sha256(re.sub(r"\s+", " ", text).strip().lower().encode()).hexdigest()
    example = TrainingExample.objects.create(
        text=text, source="manual", labels=values["labels"], group_sha=digest, approved=values["approved"],
        reviewed_by_ref_id=actor.pk if values["approved"] else None,
    )
    Audit.objects.create(actor=actor.pk, action="ml_label", target=example.pk, details={"sha256": digest})


@transaction.atomic
def remove_example(actor, identifier):
    example = get_object_or_404(TrainingExample.objects.only("id", "dataset_id", "source"), pk=identifier)
    if example.dataset_id:
        update_dataset(actor, example.dataset_id, "delete_example", identifier)
    else:
        example = get_object_or_404(TrainingExample.objects.select_for_update(), pk=identifier)
        example.delete()
        Audit.objects.create(actor=actor.pk, action="ml_example_delete", target=identifier,
                             details={"source": example.source})


def queue_training(actor, values):
    dataset_id = values["dataset"].pk if values["dataset"] else None
    rows = corpus(dataset_id)
    with transaction.atomic():
        kind = "training.model" if values["engine"] == "tfidf" else "training.neural"
        job = enqueue(kind, {
            "name": values["name"], "engine": values["engine"], "dataset_id": dataset_id,
            "category_id": values["category"].pk if values["category"] else None,
            "min_f1": values["min_f1"], "snapshot_sha": snapshot_hash(rows),
        }, "training:" + uuid4().hex)
        Audit.objects.create(actor=actor.pk, action="model_training_requested", target=str(job.pk))


def tab_redirect(tab):
    response = redirect("models-page")
    response["Location"] += "?tab=" + tab
    return response


@require_http_methods(["GET", "POST"])
def models(request):
    denied = access(request)
    if denied is not None:
        return denied
    admin = request.user.has_perm("identity.administer")
    can_label = request.user.has_perm("identity.investigate") and request.user.has_perm("identity.view_originals")
    tab = request.GET.get("tab", "models")
    if tab in {"examples", "label"} and not can_label:
        return HttpResponseForbidden("Требуется доступ к обучающим примерам")
    action = request.POST.get("action", "")
    train_form = example_form = label_form = None
    error = ""
    if request.method == "POST":
        if action == "example":
            if not can_label:
                return HttpResponseForbidden("Требуется доступ к обучающим примерам")
            tab = "label"
            example_form = ManualExampleForm(request.POST)
            if example_form.is_valid():
                add_example(request.user, example_form.cleaned_data)
                return tab_redirect("examples")
        else:
            denied = admin_access(request)
            if denied is not None:
                return denied
            if action == "create_label":
                if not can_label:
                    return HttpResponseForbidden("Требуется доступ к обучающим примерам")
                tab = "label"
                label_form = TrainingLabelForm(request.POST)
                if label_form.is_valid():
                    with transaction.atomic():
                        # Keep label identities independent of detection categories.
                        row = Category.objects.create(pk="CUSTOM_" + uuid4().hex, mode="label",
                            group_name="ML-разметка", active=True, **label_form.cleaned_data)
                        Audit.objects.create(actor=request.user.pk, action="training_label_create", target=row.pk)
                    return tab_redirect("label")
            elif action == "train":
                denied = access(request, originals=True)
                if denied is not None:
                    return denied
                tab = "training"
                train_form = TrainingForm(request.POST)
                if train_form.is_valid():
                    try:
                        queue_training(request.user, train_form.cleaned_data)
                    except ValueError as exc:
                        train_form.add_error(None, str(exc))
                    else:
                        return tab_redirect(tab)
            elif action == "delete_example":
                denied = access(request, originals=True)
                if denied is not None:
                    return denied
                remove_example(request.user, request.POST.get("example_id"))
                return tab_redirect("examples")
            elif action in {"publish", "rollback", "deactivate", "delete"}:
                try:
                    model_action(request.user, request.POST.get("model_id"), action)
                except ValueError as exc:
                    error = str(exc)
                else:
                    return tab_redirect("models")
            else:
                return HttpResponseBadRequest("Неизвестное действие")
    if tab == "training" and admin and request.user.has_perm("identity.view_originals") and request.GET.get("new"):
        train_form = train_form or TrainingForm()
    if tab == "label" and admin:
        label_form = label_form or TrainingLabelForm()
    if tab == "label" and request.GET.get("new"):
        example_form = example_form or ManualExampleForm()
    active = MLModel.objects.filter(active=True)
    rows = MLModel.objects.select_related("category").defer("artifact").order_by("-created_at", "-pk")
    context = {"tab": tab, "admin": admin, "can_label": can_label, "train_form": train_form,
               "example_form": example_form, "error": error, "active_count": active.count(), "ml_status": ml_status()}
    if tab == "label":
        context["training_labels"] = Category.objects.filter(mode="label").order_by("name")
        context["label_form"] = label_form
    if tab == "examples":
        names = dict(Category.objects.values_list("pk", "name"))
        samples = TrainingExample.objects.defer("text").annotate(preview=Left("text", 281)).order_by("-created_at", "-pk")
        page = Paginator(samples, 50).get_page(request.GET.get("page"))
        for sample in page:
            sample.label_names = [names.get(label, label) for label in sample.labels]
        context["examples"] = page
        context["pagination_query"] = "tab=examples"
    elif tab == "training":
        context["jobs"] = WorkItem.objects.filter(kind__in=["training.model", "training.neural"]).order_by("-created_at")[:30]
    elif tab == "quality":
        context["active_models"] = rows.filter(active=True)[:100]
    else:
        context["models"] = rows[:100]
        if request.GET.get("metrics"):
            context["metric_model"] = get_object_or_404(rows, pk=request.GET["metrics"])
    return render(request, "records/models.html", context, status=400 if request.method == "POST" else 200)
