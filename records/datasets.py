"""Import and review datasets independently of inference."""

import hashlib
import json
from collections import defaultdict

import httpx
from django import forms
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Max
from django.db.models.functions import Left
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from pipeline.parser_client import call
from records.category_picker import LabelForm
from records.models import Audit, Category, MLDataset, TrainingExample
from records.workspace import access

MAX_IMPORT_BYTES = 12 * 1024**2


class DatasetImportForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=160, label="Название")
    source = forms.CharField(max_length=120, initial="external-llm", required=False, label="Источник")
    description = forms.CharField(max_length=2000, required=False, label="Описание")
    file = forms.FileField(label="CSV / JSONL (UTF-8, до 12 МиБ)",
                           widget=forms.ClearableFileInput(attrs={"accept": ".csv,.jsonl"}))
    label_mapping = forms.JSONField(required=False, initial={}, label="Внешняя метка → код категории",
                                    widget=forms.Textarea(attrs={"rows": 3}))

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not value.name.lower().endswith((".csv", ".jsonl")) or not 0 < value.size <= MAX_IMPORT_BYTES:
            raise forms.ValidationError("Выберите CSV/JSONL до 12 МиБ")
        return value

    def clean_label_mapping(self):
        mapping = self.cleaned_data["label_mapping"]
        if mapping is None:
            return {}
        if (not isinstance(mapping, dict) or len(mapping) > 100
                or any(not isinstance(value, str) for value in mapping.values())):
            raise forms.ValidationError("Укажите JSON-объект, содержащий до 100 пар строк")
        return mapping


def import_rows(upload, mapping):
    raw = upload.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("Файл превышает 12 МиБ")
    categories = list(Category.objects.filter(active=True).values_list("pk", "name"))
    valid = {"NORMAL", *(pk for pk, _ in categories)}
    if not set(mapping.values()) <= valid:
        raise ValueError("В сопоставлении есть неизвестные или архивированные категории")
    category_map = {name: pk for pk, name in categories}
    category_map.update({pk: pk for pk in valid})
    category_map.update(mapping)
    try:
        result = call("dataset_import", json.dumps({
            "text": raw.decode("utf-8-sig"), "name": upload.name, "category_map": category_map,
        }, ensure_ascii=False).encode())
        rows = result["rows"]
        if not isinstance(rows, list) or not 0 < len(rows) <= 5000:
            raise ValueError
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not 10 <= len(row["text"]) <= 100000:
                raise ValueError
            labels = row.get("labels")
            if (not isinstance(labels, list) or not 1 <= len(labels) <= 20
                    or any(not isinstance(label, str) or label not in valid for label in labels)
                    or ("NORMAL" in labels and len(labels) != 1)):
                raise ValueError
    except (ValueError, KeyError, RuntimeError, httpx.HTTPError) as exc:
        raise ValueError("Импорт отклонён. Проверьте CSV/JSONL и доступность Parser.") from exc
    return rows, hashlib.sha256(raw).hexdigest()


@transaction.atomic
def save_import(actor, name, description, source, rows, fingerprint):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('ml-dataset-import'))")
    existing = MLDataset.objects.filter(fingerprint=fingerprint).first()
    if existing:
        raise ValueError(f"Этот файл уже загружен как «{existing.name}»")
    version = (MLDataset.objects.filter(name=name).aggregate(latest=Max("version"))["latest"] or 0) + 1
    dataset = MLDataset.objects.create(
        name=name, description=description, source=source, version=version, status="REVIEW",
        fingerprint=fingerprint, example_count=len(rows),
    )
    TrainingExample.objects.bulk_create([
        TrainingExample(
            dataset=dataset, source="external-llm" if source == "external-llm" else "import",
            text=row["text"], labels=row["labels"], approved=False,
            group_sha=hashlib.sha256(" ".join(row["text"].lower().split()).encode()).hexdigest(),
        ) for row in rows
    ])
    Audit.objects.create(actor=actor.pk, action="dataset_import", target=dataset.pk,
                         details={"rows": len(rows), "sha256": fingerprint, "source": source})
    return dataset


@transaction.atomic
def update_dataset(actor, dataset_id, action, example_id=None, review=None):
    dataset = get_object_or_404(MLDataset.objects.select_for_update(), pk=dataset_id)
    examples = TrainingExample.objects.filter(dataset=dataset)
    if action == "delete":
        count, _ = examples.delete()
        dataset.delete()
        Audit.objects.create(actor=actor.pk, action="dataset_delete", target=dataset_id,
                             details={"name": dataset.name, "examples_deleted": count})
        return
    example = get_object_or_404(examples.select_for_update(), pk=example_id)
    before = {"labels": example.labels, "approved": example.approved}
    if action == "delete_example":
        example.delete()
    else:
        example.labels = review["labels"]
        example.approved = review["approved"]
        example.reviewed_by_ref_id = actor.pk
        example.save(update_fields=["labels", "approved", "reviewed_by_ref"])
    dataset.example_count = examples.count()
    dataset.status = "REVIEW" if not dataset.example_count or examples.filter(approved=False).exists() else "READY"
    dataset.save(update_fields=["example_count", "status"])
    Audit.objects.create(actor=actor.pk, action="dataset_" + action, target=example_id,
                         details={"dataset": dataset_id, "before": before, **(review or {})})


def dataset_stats(examples):
    labels = defaultdict(lambda: {"total": 0, "approved": 0})
    total = approved_count = 0
    for example_labels, approved in examples.values_list("labels", "approved").iterator():
        total += 1
        approved_count += int(approved)
        for label in example_labels:
            labels[label]["total"] += 1
            labels[label]["approved"] += int(approved)
    return total, approved_count, sorted(labels.items())


@require_http_methods(["GET", "POST"])
def datasets(request, dataset_id=None):
    for permission in ({"write": True}, {"originals": True}):
        denied = access(request, **permission)
        if denied is not None:
            return denied
    admin = request.user.has_perm("identity.administer")
    dataset = get_object_or_404(MLDataset, pk=dataset_id) if dataset_id else None
    url = ("dataset-detail", dataset_id) if dataset else ("datasets-page",)
    action = request.POST.get("action")
    import_form = review_form = example = None
    if request.method == "POST":
        if not dataset and action == "import":
            if not admin:
                return HttpResponseForbidden("Недостаточно прав")
            import_form = DatasetImportForm(request.POST, request.FILES)
            if import_form.is_valid():
                values = import_form.cleaned_data
                try:
                    rows, fingerprint = import_rows(values["file"], values["label_mapping"])
                    imported = save_import(request.user, values["name"], values["description"],
                                           values["source"], rows, fingerprint)
                except ValueError as exc:
                    import_form.add_error(None, str(exc))
                else:
                    return redirect("dataset-detail", imported.pk)
        elif dataset and action in {"delete", "delete_example"}:
            if not admin:
                return HttpResponseForbidden("Недостаточно прав")
            update_dataset(request.user, dataset_id, action, request.POST.get("example_id"))
            return redirect(*url) if action == "delete_example" else redirect("datasets-page")
        elif not dataset or action != "review":
            return HttpResponseBadRequest("Неизвестное действие")
    if admin and not dataset and request.GET.get("import") and import_form is None:
        import_form = DatasetImportForm()
    if dataset and (request.GET.get("edit") or action == "review"):
        example = get_object_or_404(TrainingExample, dataset=dataset,
                                    pk=request.POST.get("example_id") or request.GET.get("edit"))
        review_form = LabelForm(request.POST if action == "review" else None,
                                        initial={"labels": example.labels, "approved": example.approved})
        if action == "review" and review_form.is_valid():
            update_dataset(request.user, dataset_id, action, example.pk, review_form.cleaned_data)
            location = redirect(*url)
            page = request.GET.get("page", "")
            if page.isdecimal():
                location["Location"] += "?page=" + page
            return location
    context = {"datasets": MLDataset.objects.order_by("-created_at")[:100], "dataset": dataset,
               "import_form": import_form, "admin": admin, "review_form": review_form, "review_example": example}
    if dataset:
        examples = TrainingExample.objects.filter(dataset=dataset).defer("text").order_by("created_at", "pk")
        total, approved, labels = dataset_stats(examples)
        page = Paginator(examples.annotate(preview=Left("text", 301)), 20).get_page(request.GET.get("page"))
        context.update(examples=page, total=total, approved_count=approved, stats=labels)
    return render(request, "records/datasets.html", context, status=400 if request.method == "POST" else 200)
