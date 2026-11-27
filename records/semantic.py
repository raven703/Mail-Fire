"""Native pgvector indexing/search; embeddings are loaded only by optional workers."""

import math
import os
from functools import lru_cache
from uuid import uuid4

from django import forms
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from pgvector.django import CosineDistance

from pipeline.models import WorkItem
from pipeline.services import enqueue, finish, locked_current
from records.models import Audit, Content, Reference, SemanticChunk
from records.workspace import access

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def encoder():
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL, cache_dir=os.getenv("EMBEDDING_CACHE_DIR", "/opt/embedding-models"),
                         threads=2, local_files_only=True)


def chunks(value):
    words = value.split()
    return [" ".join(words[index:index + 180]) for index in range(0, len(words), 140)]


def vectors(parts):
    result = []
    for item in encoder().embed(parts):
        value = [float(number) for number in item]
        if len(value) != 384 or any(not math.isfinite(number) for number in value) or not any(value):
            raise ValueError("Invalid embedding")
        result.append(value)
    if len(result) != len(parts):
        raise ValueError("Incomplete embeddings")
    return result


def reindex(job):
    completed = job.output.get("completed", 0)
    for kind, identifier in job.payload["items"][completed:]:
        model = Reference if kind == "reference" else Content
        source = model.objects.filter(pk=identifier).first()
        parts = chunks(source.text) if source and not (kind == "reference" and source.fingerprint.get("document_template")) else []
        if len(parts) > 5000:
            raise ValueError("Document chunk limit")
        embeddings = vectors(parts) if parts else []
        with transaction.atomic():
            current = locked_current(job.pk, job.token)
            # Match retention/GC's source lock and reject stale extraction.
            row = model.objects.select_for_update().filter(pk=identifier).first()
            if row and source and row.text != source.text:
                raise ValueError("Source changed during indexing")
            SemanticChunk.objects.filter(source_type=kind, source_id=identifier).delete()
            if row and not (kind == "reference" and row.fingerprint.get("document_template")):
                SemanticChunk.objects.bulk_create([
                    SemanticChunk(source_type=kind, source_id=identifier, chunk_index=index,
                                  text=part, model=MODEL, embedding=embedding)
                    for index, (part, embedding) in enumerate(zip(parts, embeddings))
                ], batch_size=100)
            completed += 1
            current.output = {"completed": completed, "total": len(job.payload["items"])}
            current.save(update_fields=["output"])
    with transaction.atomic():
        locked_current(job.pk, job.token)
        finish(job.pk, job.token, {"completed": completed, "total": len(job.payload["items"])})


def search_job(job):
    embedding = vectors([job.payload["query"]])[0]
    rows = SemanticChunk.objects.filter(model=MODEL)
    if job.payload.get("source_type"):
        rows = rows.filter(source_type=job.payload["source_type"])
    found = list(rows.annotate(distance=CosineDistance("embedding", embedding)).order_by("distance")
                 .values("source_type", "source_id", "chunk_index", "text", "distance")[:20])
    with transaction.atomic():
        locked_current(job.pk, job.token)
        finish(job.pk, job.token, {"items": found, "model": MODEL})


class SearchForm(forms.Form):
    query = forms.CharField(min_length=3, max_length=10000, widget=forms.Textarea)
    source_type = forms.ChoiceField(required=False, choices=[("", "Все"), ("content", "Письма"), ("reference", "Эталоны")])


@require_http_methods(["GET", "POST"])
def page(request):
    error = access(request, originals=True)
    if error is not None:
        return error
    form = SearchForm(request.POST if request.method == "POST" and request.POST.get("action") == "search" else None)
    if request.method == "POST":
        if request.POST.get("action") == "reindex":
            error = access(request, write=True)
            if error is not None:
                return error
            items = []
            for kind, model in [("reference", Reference), ("content", Content)]:
                items.extend([[kind, pk] for pk in model.objects.order_by("pk").values_list("pk", flat=True)[:10001]])
            if len(items) > 10000:
                form = SearchForm({})
                form.is_valid()
                form.add_error(None, "Не более 10000 документов за один запуск")
            else:
                with transaction.atomic():
                    job = enqueue("semantic.reindex", {"items": items, "actor": request.user.pk}, "reindex:" + uuid4().hex)
                    Audit.objects.create(actor=request.user.pk, action="semantic_reindex", target=str(job.pk))
                return redirect("semantic-page")
        elif form.is_valid():
            with transaction.atomic():
                job = enqueue("semantic.search", {**form.cleaned_data, "actor": request.user.pk}, "search:" + uuid4().hex)
                Audit.objects.create(actor=request.user.pk, action="semantic_search", target=str(job.pk))
            return redirect("semantic-page")
    return render(request, "records/semantic.html", {
        "form": form, "counts": SemanticChunk.objects.values("source_type", "model").annotate(count=Count("pk")),
        "jobs": WorkItem.objects.filter(kind__in=["semantic.search", "semantic.reindex"], payload__actor=request.user.pk).order_by("-created_at")[:20],
    })