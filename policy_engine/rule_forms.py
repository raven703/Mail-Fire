"""Structured controls for the unchanged category-rule configuration contract."""
from django import forms

from policy_engine.rule_config import validate_config
from records.models import CategoryRule, Reference


class StructuredRuleForm(forms.ModelForm):
    phrases = forms.CharField(required=False, label="Ключевые фразы — по одной на строку", widget=forms.Textarea(attrs={"rows": 4}))
    exclude_phrases = forms.CharField(required=False, label="Исключающие фразы — по одной на строку", widget=forms.Textarea(attrs={"rows": 3}))
    match_type = forms.ChoiceField(required=False, initial="substring", label="Сопоставление", choices=[
        ("substring", "Подстрока"), ("word", "Целое слово"), ("morphology", "Морфология"), ("flexible", "Гибкое совпадение")])
    min_score = forms.IntegerField(required=False, initial=1, min_value=1, max_value=1000, label="Минимальная сумма весов")
    window = forms.IntegerField(required=False, initial=12, min_value=1, max_value=80, label="Окно слов")
    ordered = forms.BooleanField(required=False, label="Учитывать порядок терминов")
    pattern = forms.CharField(required=False, label="Безопасный Regex", max_length=120)
    reference_ids = forms.MultipleChoiceField(required=False, label="Эталонные документы", widget=forms.CheckboxSelectMultiple)
    min_similarity = forms.FloatField(required=False, initial=.8, min_value=.5, max_value=1, label="Минимальное сходство")
    min_confidence = forms.FloatField(required=False, initial=.7, min_value=0, max_value=1, label="Минимальная уверенность ML")

    class Meta:
        model = CategoryRule
        fields = ["title", "kind", "risk", "priority", "enabled"]
        widgets = {"kind": forms.Select(choices=[("keywords", "Ключевые слова"), ("regex", "Безопасный Regex"),
                                                  ("reference", "Эталонные документы"), ("ml", "ML-модель")])}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reference_ids"].choices = list(Reference.objects.order_by("name").values_list("pk", "name"))
        config = self.instance.config or {}
        for key in ("phrases", "exclude_phrases"):
            self.initial[key] = "\n".join(config.get(key, []))
        for key in ("match_type", "min_score", "window", "ordered", "pattern", "reference_ids", "min_similarity", "min_confidence"):
            if key in config:
                self.initial[key] = config[key]
        terms = config.get("terms", [])
        for index in range(30):
            term = terms[index] if index < len(terms) else {}
            self.fields[f"term_{index}_text"] = forms.CharField(required=False, max_length=120, initial=term.get("text", ""), label="Термин")
            self.fields[f"term_{index}_weight"] = forms.IntegerField(required=False, min_value=1, max_value=100, initial=term.get("weight", 1), label="Вес")
            self.fields[f"term_{index}_required"] = forms.BooleanField(required=False, initial=term.get("required", False), label="Обязательный")
        self.term_rows = [(self[f"term_{i}_text"], self[f"term_{i}_weight"], self[f"term_{i}_required"]) for i in range(30)]

    def clean(self):
        values = super().clean()
        if self.errors:
            return values
        kind = values.get("kind")
        config = {"exclude_phrases": [line.strip() for line in values.get("exclude_phrases", "").splitlines() if line.strip()]}
        if kind == "keywords":
            config.update({"phrases": [line.strip() for line in values.get("phrases", "").splitlines() if line.strip()],
                           "match_type": values.get("match_type") or "substring", "min_score": values.get("min_score") or 1,
                           "window": values.get("window") or 12, "ordered": values.get("ordered", False),
                           "terms": [{"text": values[f"term_{i}_text"], "weight": values.get(f"term_{i}_weight") or 1,
                                      "required": values.get(f"term_{i}_required", False)} for i in range(30) if values.get(f"term_{i}_text")]})
        elif kind == "regex":
            config["pattern"] = values.get("pattern", "")
        elif kind == "reference":
            config.update(reference_ids=values.get("reference_ids", []), min_similarity=values.get("min_similarity") if values.get("min_similarity") is not None else .8)
        elif kind == "ml":
            config["min_confidence"] = values.get("min_confidence") if values.get("min_confidence") is not None else .7
        try:
            self.instance.config = validate_config(kind, config)
        except (ValueError, TypeError, KeyError) as exc:
            raise forms.ValidationError(str(exc)) from exc
        if not 0 <= values.get("risk", -1) <= 100 or not 0 <= values.get("priority", -1) <= 10000:
            raise forms.ValidationError("Риск: 0–100; приоритет: 0–10000")
        return values