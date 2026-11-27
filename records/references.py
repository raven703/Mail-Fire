"""Native reference catalog. Sample personal fields never become template data."""

import hashlib
from uuid import uuid4

import httpx
from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from app.document_templates import TEMPLATES, match_document, template_config
from app.fingerprints import fingerprint
from pipeline.parser_client import call
from pipeline.services import enqueue
from records.models import Audit, Blob, Reference, SemanticChunk
from records.operations import admin_access
from records.ui_filters import pagination_query
from records.workspace import access


class ReferenceForm(forms.Form):
    file = forms.FileField(label="Документ")
    template_type = forms.ChoiceField(required=False, label="Тип эталона", choices=[
        ("", "Содержимое документа"), *[(key, value["label"]) for key, value in TEMPLATES.items()],
    ])

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not 0 < value.size <= settings.MICE_MAX_MESSAGE_BYTES:
            raise forms.ValidationError("Неверный размер документа")
        return value


def prepare_reference(data, name, kind, extracted):
    if not isinstance(extracted.get("text"), str) or not extracted["text"].strip() or extracted.get("status") not in {"ANALYZED", "PARTIAL"}:
        raise ValueError("Текст не извлечён; документ не проиндексирован")
    text = extracted["text"]
    if kind:
        spec = template_config(kind)
        if not match_document(text, spec):
            raise ValueError("Образец не подтверждает тип документа")
        return {
            "name": TEMPLATES[kind]["label"] + " — шаблон",
            "data": ("document-template:" + kind).encode(),
            "text": " ".join(spec["anchors"]), "fingerprint": {"document_template": spec},
        }
    return {"name": name[:1024], "data": data, "text": text, "fingerprint": fingerprint(text)}


@transaction.atomic
def save_reference(actor, prepared):
    data = prepared["data"]
    digest = hashlib.sha256(data).hexdigest()
    Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
    row = Reference.objects.create(
        name=prepared["name"], blob_sha_ref_id=digest, text=prepared["text"], fingerprint=prepared["fingerprint"],
    )
    Audit.objects.create(actor=actor.pk, action="reference_upload", target=row.pk,
                         details={"template": "document_template" in row.fingerprint})
    if settings.MICE_SEMANTIC_AUTO_INDEX and "document_template" not in row.fingerprint:
        enqueue("semantic.reindex", {"items": [["reference", row.pk]], "actor": actor.pk},
                "reference-upload:" + row.pk)
    return row


def indexed_references():
    from records.semantic import MODEL
    chunks = SemanticChunk.objects.filter(source_type="reference", source_id=OuterRef("pk"), model=MODEL).order_by()
    return Reference.objects.annotate(
        chunk_count=Subquery(chunks.values("source_id").annotate(count=Count("pk")).values("count")),
    )


def reference_matches(identifier):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT i.id, m.subject, i.created_at, f->>'confidence', f->>'excerpt'
                       FROM incidents i JOIN messages m ON m.id=i.message_id
                       CROSS JOIN LATERAL jsonb_array_elements(i.findings) AS f
                       WHERE f->>'rule_id'=%s ORDER BY i.created_at DESC LIMIT 100""", [identifier])
        return [dict(zip(("id", "subject", "at", "confidence", "excerpt"), row, strict=True))
                for row in cursor.fetchall()]


@transaction.atomic
def update_reference(actor, identifier, action):
    row = get_object_or_404(Reference.objects.select_for_update().defer("text"), pk=identifier)
    if action == "delete":
        SemanticChunk.objects.filter(source_type="reference", source_id=row.pk).delete()
        row.delete()
        Audit.objects.create(actor=actor.pk, action="reference_delete", target=identifier)
    else:
        if row.fingerprint.get("document_template"):
            raise ValueError("Для шаблонов документов семантический индекс не используется")
        job = enqueue("semantic.reindex", {"items": [["reference", row.pk]], "actor": actor.pk},
                      "reindex:" + uuid4().hex)
        Audit.objects.create(actor=actor.pk, action="reference_reindex", target=row.pk,
                             details={"job": str(job.pk)})


@require_http_methods(["GET", "POST"])
def references(request, reference_id=None):
    denied = access(request, originals=True)
    if denied is not None:
        return denied
    can_edit = request.user.has_perm("identity.investigate")
    admin = request.user.has_perm("identity.administer")
    form = None
    error = ""
    action = request.POST.get("action", "upload")
    if request.method == "POST":
        if reference_id and action in {"delete", "reindex"}:
            denied = admin_access(request) if action == "delete" else access(request, write=True)
            if denied is not None:
                return denied
            try:
                update_reference(request.user, reference_id, action)
            except ValueError as exc:
                error = str(exc)
            else:
                return redirect("references-page")
        elif not reference_id and action == "upload":
            denied = access(request, write=True)
            if denied is not None:
                return denied
            form = ReferenceForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data["file"]
                data = upload.read(settings.MICE_MAX_MESSAGE_BYTES + 1)
                try:
                    if not 0 < len(data) <= settings.MICE_MAX_MESSAGE_BYTES:
                        raise ValueError("Неверный размер документа")
                    extracted = call("extract", data, upload.name, ocr=True)
                    prepared = prepare_reference(data, upload.name, form.cleaned_data["template_type"], extracted)
                except (ValueError, KeyError, TypeError, RuntimeError, httpx.HTTPError):
                    form.add_error(None, "Документ не принят. Проверьте текст, тип образца и доступность Parser/OCR.")
                else:
                    save_reference(request.user, prepared)
                    return redirect("references-page")
        else:
            return HttpResponseBadRequest("Неизвестное действие")
    elif can_edit and request.GET.get("new"):
        form = ReferenceForm()
    context = {"form": form, "error": error, "can_edit": can_edit, "admin": admin}
    if reference_id:
        details = indexed_references().select_related("blob_sha_ref").defer("blob_sha_ref__data")
        if request.GET.get("settings") or request.method == "POST":
            context["settings_row"] = get_object_or_404(details.defer("text"), pk=reference_id)
        else:
            row = get_object_or_404(details, pk=reference_id)
            Audit.objects.create(actor=request.user.pk, action="reference_view", target=row.pk)
            context.update(view_row=row, matches=reference_matches(row.pk))
    query = request.GET.get("q", "").strip()[:200]
    rows = indexed_references().filter(name__icontains=query).order_by("-created_at", "-pk")
    stats = rows.aggregate(total=Count("pk"), indexed=Count("pk", filter=Q(chunk_count__gt=0)),
                           bytes=Sum("blob_sha_ref__size", default=0))
    page = Paginator(rows.select_related("blob_sha_ref").defer("text", "blob_sha_ref__data"), 50).get_page(request.GET.get("page"))
    context.update(page=page, stats=stats, query=query, pagination_query=pagination_query(request.GET))
    return render(request, "records/references.html", context, status=400 if request.method == "POST" else 200)
