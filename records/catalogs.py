"""Native employee and email-address catalog with auditable changes."""

from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from records.models import Address, Audit, Identity
from records.operations import admin_access


class EmployeeForm(forms.ModelForm):
    name = forms.CharField(max_length=200, label="ФИО")
    department = forms.CharField(max_length=200, required=False, label="Подразделение")

    class Meta:
        model = Identity
        fields = ["name", "department"]


class AddressForm(forms.ModelForm):
    email = forms.EmailField(max_length=320)
    kind = forms.ChoiceField(choices=[(value, value) for value in ("unknown", "internal", "external")])

    class Meta:
        model = Address
        fields = ["email", "identity", "kind"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identity"].label_from_instance = lambda row: row.name

    def clean_email(self):
        value = self.cleaned_data["email"].strip().lower()
        if Address.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Адрес уже существует")
        return value


@require_http_methods(["GET", "POST"])
def catalog(request, kind, object_id=None):
    error = admin_access(request)
    if error is not None:
        return error
    model, form_class = (Identity, EmployeeForm) if kind == "employees" else (Address, AddressForm)
    row = get_object_or_404(model, pk=object_id) if object_id else None
    form = form_class(request.POST if request.method == "POST" else None, instance=row)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if row:
                model.objects.select_for_update().get(pk=row.pk)
            row = form.save()
            Audit.objects.create(actor=request.user.pk, action=kind + "_update", target=row.pk)
        return redirect("employees-page" if kind == "employees" else "addresses-page")
    query = request.GET.get("q", "").strip()
    rows = model.objects.order_by("name" if kind == "employees" else "email")
    if query:
        rows = rows.filter(**{("name__icontains" if kind == "employees" else "email__icontains"): query})
    if kind != "employees":
        rows = rows.select_related("identity")
    return render(request, "records/catalog.html", {
        "kind": kind, "form": form, "query": query, "page": Paginator(rows, 50).get_page(request.GET.get("page")),
    }, status=400 if form.is_bound else 200)