"""Two-step package import; preview stores only a digest in the session."""
import hashlib

from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.trainer_package import MAX_TOTAL
from records.operations import admin_access
from records.trainer_import import import_models, preview


@require_http_methods(["GET", "POST"])
def trainer_import(request):
    denied = admin_access(request)
    if denied is not None:
        return denied
    context = {}
    status = 200
    if request.method == "POST":
        try:
            uploaded = request.FILES.get("package")
            if not uploaded or uploaded.size > MAX_TOTAL:
                raise ValueError("Выберите ZIP допустимого размера (до 2 ГиБ)")
            checksum = hashlib.sha256()
            for chunk in uploaded.chunks():
                checksum.update(chunk)
            checksum = checksum.hexdigest()
            uploaded.seek(0)
            if request.POST.get("action") == "import":
                if request.session.get("trainer_preview") != checksum:
                    raise ValueError("Сначала просмотрите этот пакет; повторно выберите тот же файл")
                if request.POST.get("trust") != "yes":
                    return HttpResponseForbidden("Требуется явное подтверждение доверия")
                selected = None if request.POST.get("all") == "yes" else request.POST.getlist("models")
                imported = import_models(uploaded, selected, trusted=True, commit=True)
                request.session.pop("trainer_preview", None)
                context["success"] = f"Импортировано неактивных моделей: {len(imported)}. Активация выполняется вручную."
            else:
                context["manifest"] = preview(uploaded)
                request.session["trainer_preview"] = checksum
        except (OSError, ValueError, KeyError, TypeError) as exc:
            context["error"] = str(exc)
            status = 400
    template = "records/trainer_import_content.html" if request.headers.get("HX-Request") else "records/trainer_import.html"
    return render(request, template, context, status=status)