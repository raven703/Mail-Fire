from django.db import migrations

BUILTIN = [
    ("EMAIL", "Адрес электронной почты", "Персональные данные"),
    ("PHONE", "Телефон", "Персональные данные"),
    ("INN", "ИНН (правило)", "Персональные данные"),
    ("RU_INN", "ИНН (Presidio)", "Персональные данные"),
    ("RU_SNILS", "СНИЛС", "Персональные данные"),
    ("RU_PASSPORT", "Паспорт РФ", "Персональные данные"),
    ("RU_PHONE", "Телефон (Presidio)", "Персональные данные"),
    ("SECRET", "Пароли и токены", "Секреты"),
    ("PRIVATE_KEY", "Закрытый ключ", "Секреты"),
    ("CONFIDENTIAL", "Коммерческая тайна", "Конфиденциальные данные"),
    ("PROMPT_INJECTION", "Попытка изменить инструкции", "Безопасность"),
    ("CODE", "Исходный код", "Исходный код"),
    ("SUSPICIOUS_COMMAND", "Опасные команды", "Безопасность"),
    ("YARA", "YARA-сигнатура", "Безопасность"),
    ("OFFICE_MACRO", "Опасный макрос Office", "Безопасность"),
    ("MALWARE", "Вредоносный файл ClamAV", "Безопасность"),
    ("REFERENCE_DOCUMENT", "Совпадение с эталоном", "Документы"),
    ("SEMANTIC_REFERENCE", "Семантическое сходство", "Документы"),
    ("NORMAL", "Безопасный материал", "ML-разметка"),
]


def seed_system_categories(apps, schema_editor):
    category = apps.get_model("records", "Category")
    rows = category.objects.using(schema_editor.connection.alias)
    existing = dict(rows.values_list("pk", "name"))
    names = set(existing.values())
    for code, name, group in BUILTIN:
        if code in existing:
            continue
        while name in names:
            name = f"{name} ({code})"
        rows.create(pk=code, name=name, group_name=group, mode="label" if code == "NORMAL" else "builtin")
        names.add(name)


class Migration(migrations.Migration):
    dependencies = [("records", "0003_metric_service_index")]

    operations = [migrations.RunPython(seed_system_categories, migrations.RunPython.noop)]
