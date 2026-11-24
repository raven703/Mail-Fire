"""Native administrative configuration and audit; no generic arbitrary setting writes."""

from urllib.parse import urlsplit

from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from records.models import Audit, Outbox, Setting


class ConfigurationForm(forms.Form):
    normalizer_enabled = forms.BooleanField(required=False, label="Диагностика обфускации")
    normalizer_mode = forms.ChoiceField(required=False, label="Режим нормализации", choices=[
        ("detect", "Отмечать искажения"), ("augment", "Добавлять восстановленный текст в разрешённые запросы LLM"),
    ])
    sensitivity = forms.ChoiceField(choices=[(value, value) for value in ("low", "medium", "high")])
    antivirus = forms.BooleanField(required=False, label="Антивирус")
    destinations = forms.CharField(required=False, widget=forms.Textarea, label="SIEM: один URL на строку")

    def clean_destinations(self):
        values = list(dict.fromkeys(value.strip() for value in self.cleaned_data["destinations"].splitlines() if value.strip()))
        if len(values) > 30:
            raise forms.ValidationError("Максимум 30 получателей")
        for value in values:
            try:
                parsed = urlsplit(value)
                port = parsed.port
            except ValueError as exc:
                raise forms.ValidationError("Некорректный URL") from exc
            if (
                len(value) > 2048 or parsed.scheme not in {"http", "https", "syslog", "cef"}
                or not parsed.hostname or parsed.username or parsed.password or parsed.fragment
                or any(ord(char) < 33 for char in value) or (port is not None and port == 0)
            ):
                raise forms.ValidationError("Некорректный URL получателя")
        return [{"url": value, "enabled": True} for value in values]


def admin_access(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    if not request.user.has_perm("identity.administer"):
        return HttpResponseForbidden("Недостаточно прав")
    return None


@require_http_methods(["GET", "POST"])
def configuration(request):
    error = admin_access(request)
    if error is not None:
        return error
    values = {row.pk: row.value for row in Setting.objects.filter(pk__in=["normalizer", "detectors", "integrations"])}
    normalizer, detectors = values.get("normalizer", {}), values.get("detectors", {})
    form = ConfigurationForm(request.POST if request.method == "POST" else None, initial={
        "normalizer_enabled": normalizer.get("enabled", False), "normalizer_mode": normalizer.get("mode", "detect"), "sensitivity": normalizer.get("sensitivity", "medium"),
        "antivirus": detectors.get("antivirus", True),
        "destinations": "\n".join(row["url"] for row in values.get("integrations", {}).get("destinations", []) if row.get("enabled", True)),
    })
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Serialize writers, including the initial absent-setting case.
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext('native-configuration'))")
            row, _ = Setting.objects.get_or_create(pk="detectors", defaults={"value": {}})
            row.value = {**row.value, "antivirus": form.cleaned_data["antivirus"], "ml": False, "llm": False}
            row.save(update_fields=["value"])
            Setting.objects.update_or_create(pk="normalizer", defaults={"value": {
                "enabled": form.cleaned_data["normalizer_enabled"], "sensitivity": form.cleaned_data["sensitivity"],
                "mode": form.cleaned_data["normalizer_mode"] or normalizer.get("mode", "detect"),
            }})
            Setting.objects.update_or_create(pk="integrations", defaults={"value": {"destinations": form.cleaned_data["destinations"]}})
            Audit.objects.create(actor=request.user.pk, action="configuration_update", target="analysis/integrations")
        return redirect("configuration-page")
    return render(request, "records/configuration.html", {"form": form, "outbox": Outbox.objects.order_by("-created_at")[:100]}, status=400 if form.is_bound else 200)


@require_GET
def audit(request):
    error = admin_access(request)
    if error is not None:
        return error
    rows = Audit.objects.order_by("-created_at", "-pk")
    for field in ("actor", "action", "target"):
        if request.GET.get(field):
            rows = rows.filter(**{field: request.GET[field]})
    return render(request, "records/audit.html", {"page": Paginator(rows, 100).get_page(request.GET.get("page"))})