"""Explicit incident labeling, preserving the original opt-in training contract."""
import hashlib

from django import forms
from django.db import transaction

from records.models import Audit, Category, Incident, TrainingExample


class IncidentTrainingForm(forms.Form):
    labels = forms.MultipleChoiceField(label="Категории", widget=forms.CheckboxSelectMultiple)
    approved = forms.BooleanField(required=False, label="Разметка проверена аналитиком")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["labels"].choices = list(Category.objects.filter(active=True).order_by("group_name", "name").values_list("pk", "name"))

    def clean_labels(self):
        values = sorted(set(self.cleaned_data["labels"]))
        if not 1 <= len(values) <= 20:
            raise forms.ValidationError("Выберите от 1 до 20 категорий")
        return values


@transaction.atomic
def save_incident_example(actor, incident_id, labels, approved=False):
    if not actor.has_perm("identity.investigate") or not actor.has_perm("identity.view_originals"):
        raise PermissionError("Нет доступа к содержимому письма")
    incident = Incident.objects.select_for_update().select_related("message__content").get(pk=incident_id)
    if TrainingExample.objects.filter(source_incident=incident).exists():
        raise ValueError("Инцидент уже связан с обучающим примером")
    content = incident.message.content
    if not content or len(content.text.strip()) < 10:
        raise ValueError("Содержимое письма ещё не извлечено")
    if Category.objects.filter(active=True, pk__in=labels).count() != len(set(labels)):
        raise ValueError("Выберите действующие категории")
    text = content.text[:100000]
    example = TrainingExample.objects.create(text=text, labels=sorted(set(labels)), approved=approved,
        group_sha=hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest(),
        source_incident=incident, source="incident", reviewed_by_ref_id=actor.pk if approved else None)
    Audit.objects.create(actor=actor.pk, action="ml_label_from_incident", target=incident.pk,
                         details={"categories": example.labels, "approved": approved})
    return example