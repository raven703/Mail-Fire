"""Dataset import/review without enabling ML/LLM inference or training."""

import hashlib
import json

import httpx
from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from pipeline.parser_client import call
from records.models import Audit, Category, MLDataset, MLModel, TrainingExample


class DatasetImportForm(forms.Form):
    name = forms.CharField(max_length=160, label="Название")
    description = forms.CharField(max_length=2000, required=False, widget=forms.Textarea, label="Описание")
    file = forms.FileField(label="CSV / JSONL (UTF-8)")

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not value.name.lower().endswith((".csv", ".jsonl")) or not 0 < value.size <= 10 * 1024**2:
            raise forms.ValidationError("CSV/JSONL до 10 МБ")
        return value


@transaction.atomic
def save_import(actor, name, description, rows):
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    dataset = MLDataset.objects.create(
        name=name, description=description, source="external", fingerprint=fingerprint, example_count=len(rows),
    )
    TrainingExample.objects.bulk_create([
        TrainingExample(
            dataset=dataset, source="external", text=row["text"], labels=row["labels"], approved=False,
            group_sha=hashlib.sha256(" ".join(row["text"].lower().split()).encode()).hexdigest(),
        ) for row in rows
    ])
    Audit.objects.create(actor=actor.pk, action="dataset_import", target=dataset.pk, details={"rows": len(rows), "sha256": fingerprint})
    return dataset


@require_http_methods(["GET", "POST"])
def datasets(request, dataset_id=None):
    if not request.user.is_authenticated:
        return redirect("login-page")
    if not request.user.has_perm("identity.administer"):
        return HttpResponseForbidden("Недостаточно прав")
    # Dataset text is sensitive content just like message evidence.
    if not request.user.has_perm("identity.view_originals"):
        return HttpResponseForbidden("Требуется доступ к исходным данным")
    dataset = get_object_or_404(MLDataset, pk=dataset_id) if dataset_id else None
    form = DatasetImportForm(request.POST if request.method == "POST" and not dataset else None,
                             request.FILES if request.method == "POST" and not dataset else None)
    error = None
    if request.method == "POST":
        if dataset:
            action = request.POST.get("action")
            if action not in {"approve", "reject"}:
                return HttpResponseForbidden("Неизвестное действие")
            with transaction.atomic():
                MLDataset.objects.select_for_update().get(pk=dataset.pk)
                example = get_object_or_404(TrainingExample.objects.select_for_update(), pk=request.POST.get("example_id"), dataset=dataset)
                example.approved = action == "approve"
                example.reviewed_by_ref_id = request.user.pk
                example.save(update_fields=["approved", "reviewed_by_ref"])
                Audit.objects.create(actor=request.user.pk, action="dataset_" + action, target=example.pk)
            return redirect("dataset-detail", dataset_id=dataset.pk)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            raw = upload.read(10 * 1024**2 + 1)
            category_map = {"NORMAL": "NORMAL"}
            for category in Category.objects.filter(active=True):
                category_map[category.pk] = category.pk
                category_map[category.name] = category.pk
            try:
                if len(raw) > 10 * 1024**2:
                    raise ValueError("Dataset size limit")
                result = call("dataset_import", json.dumps({
                    "text": raw.decode("utf-8-sig"), "name": upload.name, "category_map": category_map,
                }).encode())
                rows = result["rows"]
                if not isinstance(rows, list) or not 0 < len(rows) <= 5000:
                    raise ValueError("Invalid dataset response")
                # Validate sandbox response before database writes, including labels.
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not 10 <= len(row["text"]) <= 100000:
                        raise ValueError("Invalid example")
                    labels = row.get("labels")
                    if not isinstance(labels, list) or not 1 <= len(labels) <= 20 or any(not isinstance(label, str) or label not in category_map.values() for label in labels):
                        raise ValueError("Invalid labels")
                    if "NORMAL" in labels and len(labels) != 1:
                        raise ValueError("Contradictory labels")
                dataset = save_import(request.user, form.cleaned_data["name"], form.cleaned_data["description"], rows)
            except (ValueError, KeyError, RuntimeError, httpx.HTTPError):
                form.add_error(None, "Импорт отклонён. Проверьте CSV/JSONL и доступность изолированного Parser.")
            else:
                return redirect("dataset-detail", dataset_id=dataset.pk)
    return render(request, "records/datasets.html", {
        "datasets": MLDataset.objects.order_by("-created_at"), "dataset": dataset, "form": form, "error": error,
        "examples": Paginator(TrainingExample.objects.filter(dataset=dataset).order_by("created_at"), 25).get_page(request.GET.get("page")) if dataset else [],
        "models": MLModel.objects.order_by("-created_at")[:50],
    }, status=400 if form.is_bound else 200)