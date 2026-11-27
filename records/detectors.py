"""Native controls for the detector switches used during policy evaluation."""

from django import forms
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from app.text_normalizer import DEFAULTS
from policy_engine.catalog import DETECTORS
from records.ml_status import ml_status
from records.models import Audit, Setting
from records.operations import admin_access
from records.workspace import access


class DetectorForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Включить детектор")


class SemanticForm(DetectorForm):
    threshold = forms.FloatField(min_value=0.01, max_value=1.0, label="Порог косинусного сходства")


class HorizonForm(DetectorForm):
    device = forms.ChoiceField(choices=[("cpu", "CPU"), ("cuda", "GPU (CUDA, требуется подготовленный worker)")], initial="cpu", label="Устройство Horizon")


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
    if name == "semantic" and "threshold" in values:
        Setting.objects.update_or_create(pk="semantic_detection", defaults={"value": {"threshold": values["threshold"]}})
    if name == "horizon" and "device" in values:
        Setting.objects.update_or_create(pk="horizon_detection", defaults={"value": {"device": values["device"]}})
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
    stored = dict(Setting.objects.filter(pk__in=["detectors", "normalizer", "semantic_detection"]).values_list("pk", "value"))
    flags = stored.get("detectors", {})
    normalizer = {**DEFAULTS, **stored.get("normalizer", {})}
    from records.semantic_status import semantic_status
    semantic = semantic_status(flags, stored.get("semantic_detection"))
    from records.horizon_status import horizon_status
    horizon = horizon_status(flags)
    rows = {}
    for key, (title, engine, categories) in DETECTORS.items():
        if key == "ml":
            rows[key] = {"id": key, "name": title, "engine": engine, "categories": categories, **ml_status()}
            continue
        available = key != "antivirus" or bool(settings.MICE_CLAMAV_HOST)
        rows[key] = {"id": key, "name": title, "engine": engine, "categories": categories, "available": available,
                     "enabled": normalizer["enabled"] if key == "normalizer" else available and flags.get(key, True)}
    rows["semantic"]["readiness"] = semantic
    rows["semantic"]["enabled"] = semantic["configured"]
    rows['horizon'].update(readiness=horizon, enabled=horizon['configured'])
    form = None
    if selected:
        form_class = NormalizerForm if selected == "normalizer" and request.POST.get("action") != "toggle" else DetectorForm
        initial = normalizer if selected == "normalizer" else {"enabled": flags.get(selected, selected != 'horizon') and selected != "ml"}
        if selected == "semantic" and request.POST.get("action") != "toggle":
            form_class = SemanticForm
            initial["threshold"] = semantic["threshold"]
        if selected == "horizon" and request.POST.get("action") != "toggle":
            form_class = HorizonForm
            row = Setting.objects.filter(pk="horizon_detection").first()
            initial["device"] = (row.value if row else {}).get("device", "cpu")
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
