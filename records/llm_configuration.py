"""LLM configuration only; never invokes providers or enables inference."""

from urllib.parse import urlsplit

from django import forms
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from records.models import Audit, Category, Setting
from records.operations import admin_access


class LLMForm(forms.Form):
    base_url = forms.CharField(max_length=2048, required=False)
    model = forms.CharField(max_length=160, required=False)
    routing = forms.ChoiceField(choices=[(value, value) for value in ("uncertain", "selected", "both")])
    categories = forms.ModelMultipleChoiceField(queryset=Category.objects.none(), required=False)
    min_confidence = forms.FloatField(min_value=0, max_value=1, initial=0.75)
    timeout_seconds = forms.IntegerField(min_value=2, max_value=120, initial=30)
    max_chars = forms.IntegerField(min_value=200, max_value=20000, initial=8000)
    allow_external_content = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categories"].queryset = Category.objects.filter(active=True).order_by("name")

    def clean_base_url(self):
        value = self.cleaned_data["base_url"].strip().rstrip("/")
        if value:
            parsed = urlsplit(value)
            try:
                port = parsed.port
            except ValueError as exc:
                raise forms.ValidationError("Некорректный порт") from exc
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or port == 0 or any(ord(char) < 33 for char in value):
                raise forms.ValidationError("HTTPS endpoint без credentials/query/fragment")
        return value


@require_http_methods(["GET", "POST"])
def configuration(request):
    error = admin_access(request)
    if error is not None:
        return error
    row = Setting.objects.filter(pk="llm_analyzer").first()
    values = {"routing": "uncertain", "min_confidence": 0.75, "timeout_seconds": 30, "max_chars": 8000, **(row.value if row else {})}
    form = LLMForm(request.POST if request.method == "POST" else None, initial=values)
    if request.method == "POST" and form.is_valid():
        data = {**form.cleaned_data, "categories": [cat.pk for cat in form.cleaned_data["categories"]], "enabled": False}
        with transaction.atomic():
            Setting.objects.update_or_create(pk="llm_analyzer", defaults={"value": data})
            Audit.objects.create(actor=request.user.pk, action="llm_configuration", target="llm_analyzer",
                                 details={"enabled": False, "routing": data["routing"], "categories": data["categories"]})
        return redirect("llm-page")
    return render(request, "records/llm.html", {"form": form}, status=400 if form.is_bound else 200)