"""Admin-only deployment settings. The web process never controls Docker."""
import os

from django import forms
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from records.models import Audit, Setting
from records.operations import admin_access


KEYS = ("MICE_UNIFIED_ANALYSIS_ENABLED", "MICE_ANALYSIS_CONCURRENCY",
        "MICE_PARSER_CONCURRENCY", "MICE_SANDBOX_ADDRESS_LIMIT_MIB")


class PerformanceForm(forms.Form):
    MICE_UNIFIED_ANALYSIS_ENABLED = forms.BooleanField(required=False, label="Единый конвейер анализа")
    MICE_ANALYSIS_CONCURRENCY = forms.IntegerField(min_value=1, max_value=32, label="Параллельных заданий analysis")
    MICE_PARSER_CONCURRENCY = forms.IntegerField(min_value=1, max_value=32, label="Параллельных sandbox")
    MICE_SANDBOX_ADDRESS_LIMIT_MIB = forms.IntegerField(min_value=512, max_value=2048,
                                                       label="Адресное пространство sandbox, МиБ")

    def clean(self):
        values = super().clean()
        if values.get("MICE_UNIFIED_ANALYSIS_ENABLED") and all(k in values for k in KEYS):
            if values["MICE_ANALYSIS_CONCURRENCY"] > values["MICE_PARSER_CONCURRENCY"]:
                self.add_error("MICE_ANALYSIS_CONCURRENCY", "Число заданий не должно превышать число sandbox.")
            if values["MICE_PARSER_CONCURRENCY"] * values["MICE_SANDBOX_ADDRESS_LIMIT_MIB"] > 2048:
                self.add_error("MICE_SANDBOX_ADDRESS_LIMIT_MIB",
                               "Для штатного parser 3 ГиБ оставьте не менее 1 ГиБ для broker и helpers.")
        return values


def declared():
    return {
        "MICE_UNIFIED_ANALYSIS_ENABLED": settings.MICE_UNIFIED_ANALYSIS_ENABLED,
        "MICE_ANALYSIS_CONCURRENCY": int(os.environ.get("MICE_ANALYSIS_CONCURRENCY", "2")),
        "MICE_PARSER_CONCURRENCY": int(os.environ.get("MICE_PARSER_CONCURRENCY", "2")),
        "MICE_SANDBOX_ADDRESS_LIMIT_MIB": int(os.environ.get("MICE_SANDBOX_ADDRESS_LIMIT_MIB", "1024")),
    }


def env_text(values):
    return "\n".join(f"{key}={str(values[key]).lower()}" for key in KEYS) + "\n"


@require_http_methods(["GET", "POST"])
def performance(request):
    error = admin_access(request)
    if error is not None:
        return error
    effective = declared()
    saved = Setting.objects.filter(pk="performance_deployment").first()
    initial = {**effective, **(saved.value if saved and isinstance(saved.value, dict) else {})}
    form = PerformanceForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            Setting.objects.update_or_create(pk="performance_deployment", defaults={"value": form.cleaned_data})
            Audit.objects.create(actor=request.user.pk, action="performance_deployment_update",
                                 target="performance_deployment", details=form.cleaned_data)
        return redirect("performance-page")
    if request.method == "GET" and request.GET.get("download") == "env":
        checked = PerformanceForm(initial)
        if checked.is_valid():
            response = HttpResponse(env_text(checked.cleaned_data), content_type="text/plain; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="mice-performance.env"'
            return response
    return render(request, "records/performance.html", {
        "form": form, "declared_env": env_text(effective), "desired_env": env_text(initial),
        "pending": any(initial[key] != effective[key] for key in KEYS),
    }, status=400 if form.is_bound else 200)
