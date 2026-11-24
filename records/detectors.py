"""Native controls for the detector switches used during policy evaluation."""

from django import forms
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from app.text_normalizer import DEFAULTS
from policy_engine.catalog import DETECTORS
from records.models import Audit, Setting
from records.operations import admin_access
from records.workspace import access


class DetectorForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Включить детектор")


class NormalizerForm(DetectorForm):
    mode = forms.ChoiceField(label="Режим", choices=[
        ("detect", "Отмечать искажения"), ("augment", "Добавлять восстановленный текст в разрешённые запросы LLM"),
    ])
    sensitivity = forms.ChoiceField(label="Чувствительность", choices=[
        ("low", "Низкая"), ("medium", "Средняя"), ("high", "Высокая"),
    ])


@transaction.atomic
def update_detector(actor, name, values):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('native-configuration'))")
    if name == "normalizer":
        key, action = name, "normalizer_config"
        stored = values
    else:
        key, action = "detectors", "detector_config"
        row = Setting.objects.filter(pk=key).first()
        stored = {**(row.value if row else {}), name: values["enabled"]}
    Setting.objects.update_or_create(pk=key, defaults={"value": stored})
    Audit.objects.create(actor=actor.pk, action=action, target=name, details=values)


@require_http_methods(["GET", "POST"])
def detectors(request):
    denied = access(request)
    if denied is not None:
        return denied
    admin = request.user.has_perm("identity.administer")
    selected = request.POST.get("detector") if request.method == "POST" else request.GET.get("edit")
    if selected and selected not in DETECTORS:
        return HttpResponseBadRequest("Неизвестный детектор")
    stored = dict(Setting.objects.filter(pk__in=["detectors", "normalizer"]).values_list("pk", "value"))
    flags = stored.get("detectors", {})
    normalizer = {**DEFAULTS, **stored.get("normalizer", {})}
    rows = {}
    for key, (title, engine, categories) in DETECTORS.items():
        available = key != "ml" and (key != "antivirus" or bool(settings.MICE_CLAMAV_HOST))
        rows[key] = {"id": key, "name": title, "engine": engine, "categories": categories, "available": available,
                     "enabled": normalizer["enabled"] if key == "normalizer" else available and flags.get(key, True)}
    form = None
    if selected:
        form_class = NormalizerForm if selected == "normalizer" and request.POST.get("action") != "toggle" else DetectorForm
        initial = normalizer if selected == "normalizer" else {"enabled": flags.get(selected, True) and selected != "ml"}
        form = form_class(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST":
        denied = admin_access(request)
        if denied is not None:
            return denied
        if not selected or selected == "ml":
            return HttpResponseBadRequest("Изменение недоступно")
        if form.is_valid():
            values = form.cleaned_data
            if selected == "normalizer" and request.POST.get("action") == "toggle":
                values = {**normalizer, "enabled": values["enabled"]}
            update_detector(request.user, selected, values)
            return redirect("detectors-page")
    return render(request, "records/detectors.html", {
        "rows": rows.values(), "selected": rows.get(selected), "form": form, "admin": admin,
    }, status=400 if request.method == "POST" else 200)
