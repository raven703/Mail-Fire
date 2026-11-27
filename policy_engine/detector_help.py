"""Read-only catalog documentation; no detection or database side effects.
Descriptions describe implemented mechanisms, not live service health.
Keep in sync with the referenced implementations.
"""

BUILTIN_HELP = {
    "EMAIL": {
        "description": "Адреса электронной почты в извлечённом тексте.",
        "method": "Текстовое регулярное выражение.",
        "risk": "20",
        "limitations": "Формат адреса; существование почтового ящика не проверяется.",
        "source": "app/detectors.py"
    },
    "PHONE": {
        "description": "Российские телефонные номера.",
        "method": "Регулярное выражение для номера российского формата.",
        "risk": "60",
        "limitations": "Не проверяет принадлежность номера, его доступность или связь с конкретным человеком.",
        "source": "app/detectors.py"
    },
    "INN": {
        "description": "ИНН физических и юридических лиц.",
        "method": "Числовой формат и проверка контрольных цифр. При наличии эталона типа свидетельства дополнительно проверяется структура документа.",
        "risk": "60; документ-шаблон: 75",
        "limitations": "Не проверяет регистрацию в ФНС. Исторический идентификатор RU_INN объединяется с INN.",
        "source": "app/detectors.py; app/document_templates.py"
    },
    "RU_SNILS": {
        "description": "Страховые номера индивидуального лицевого счёта.",
        "method": "Формат СНИЛС, контрольная сумма и локальный контекст для предполагаемых реквизитов. Поддерживается эталон типа страхового свидетельства.",
        "risk": "60 — валидная сумма; 40 — предполагаемый; шаблон: 75 или 40",
        "limitations": "Контрольная сумма не подтверждает выдачу номера. Предполагаемые совпадения требуют проверки.",
        "source": "app/snils.py; app/advanced_detectors.py; app/document_templates.py"
    },
    "RU_PASSPORT": {
        "description": "Серия и номер паспорта гражданина РФ.",
        "method": "Проверка формата реквизитов в локальном паспортном контексте; при наличии настроенного эталона — распознавание структуры бланка.",
        "risk": "60; документ-шаблон: 75",
        "limitations": "Не проверяет действительность паспорта по реестру. Для сканов зависит от качества извлечения текста.",
        "source": "app/passport.py; app/document_templates.py"
    },
    "SECRET": {
        "description": "Признаки паролей, ключей API и токенов в тексте и вложениях.",
        "method": "Статическое текстовое правило и Gitleaks для содержимого вложений. Gitleaks возвращает идентификатор сработавшей сигнатуры.",
        "risk": "85 — текст; 90 — Gitleaks",
        "limitations": "Совпадение не доказывает действительность секрета. Набор Gitleaks зависит от установленной версии; при недоступности сканера проверка не выполнена.",
        "source": "app/detectors.py; app/secret_scan.py"
    },
    "PRIVATE_KEY": {
        "description": "Заголовки закрытых ключей в текстовом содержимом.",
        "method": "Текстовые сигнатуры форматов PEM (в том числе RSA, EC, OpenSSH).",
        "risk": "95",
        "limitations": "Не проверяет криптографическую корректность ключа или его использование.",
        "source": "app/detectors.py"
    },
    "CONFIDENTIAL": {
        "description": "Явные грифы и пометки конфиденциальности.",
        "method": "Статический текстовый поиск обозначений коммерческой тайны и конфиденциальности.",
        "risk": "65",
        "limitations": "Не определяет юридический статус документа и не заменяет смысловую классификацию.",
        "source": "app/detectors.py"
    },
    "PROMPT_INJECTION": {
        "description": "Признаки попытки изменить инструкции системы анализа.",
        "method": "Статические текстовые сигнатуры на русском и английском языках.",
        "risk": "60",
        "limitations": "Совпадение требует проверки контекста; не подтверждает успешность атаки.",
        "source": "app/detectors.py"
    },
    "CODE": {
        "description": "Признаки исходного кода, SQL и скриптов.",
        "method": "Текстовые эвристики синтаксиса; риск повышается при сочетании локальных признаков конфиденциальности и передачи.",
        "risk": "15; 65 при дополнительном контексте",
        "limitations": "Не выполняет код и не устанавливает факт утечки.",
        "source": "app/detectors.py"
    },
    "SUSPICIOUS_COMMAND": {
        "description": "Признаки потенциально опасных команд в тексте.",
        "method": "Статические эвристики командных оболочек и сценариев.",
        "risk": "80",
        "limitations": "Команды не исполняются; совпадение не доказывает злонамеренность.",
        "source": "app/detectors.py"
    },
    "YARA": {
        "description": "Статические признаки подозрительных вложений и исполняемых файлов.",
        "method": "Встроенные YARA-сигнатуры: Suspicious_Encoded_PowerShell, Executable_PE, EICAR_Test_File.",
        "risk": "85",
        "limitations": "Срабатывание не равнозначно подтверждённому вредоносному ПО. Код не исполняется.",
        "source": "app/advanced_detectors.py"
    },
    "OFFICE_MACRO": {
        "description": "Подозрительные признаки VBA-макросов в поддерживаемых вложениях Office.",
        "method": "oletools: группы AutoExec, Suspicious и IOC.",
        "risk": "80",
        "limitations": "Наличие макроса или отдельного признака не доказывает вредоносность; макросы не исполняются.",
        "source": "app/advanced_detectors.py"
    },
    "MALWARE": {
        "description": "Файлы, распознанные антивирусом как вредоносные.",
        "method": "ClamAV через INSTREAM; результат FOUND с названием сигнатуры.",
        "risk": "100",
        "limitations": "Зависит от доступности сервиса и версии антивирусной базы. Ошибка проверки не означает чистый файл.",
        "source": "app/antivirus.py"
    },
    "REFERENCE_DOCUMENT": {
        "description": "Совпадение текста с зарегистрированным эталонным документом.",
        "method": "Сравнение SHA-256 нормализованного текста и общих последовательностей из пяти слов. Отпечаток также хранит MinHash; решение в текущем коде основано на точном совпадении или покрытии эталона и общих фрагментах.",
        "risk": "75",
        "limitations": "Требует зарегистрированного эталона. Пересечение текста не доказывает нарушение политики.",
        "source": "app/fingerprints.py; app/detection_evidence.py"
    },
    "SEMANTIC_REFERENCE": {
        "description": "Категория семантического сходства с эталоном.",
        "method": "Локальная Multilingual MiniLM: косинусное сходство фрагментов письма и индексированных эталонов в pgvector.",
        "risk": "50 — вероятностный признак",
        "limitations": "Требует включённого semantic worker и индексированных эталонов. Сходство не доказывает утечку; порог требует калибровки.",
        "source": "records/semantic.py; pipeline/semantic_detection.py"
    }
}

DETAILS = {
    "EMAIL": [
        "Один текстовый шаблон; совпадение формата адреса достаточно.",
        "Текст письма и извлечённый текст вложений."
    ],
    "PHONE": [
        "Один текстовый шаблон российского номера с допустимыми разделителями.",
        "Текст письма и извлечённый текст вложений."
    ],
    "INN": [
        "Числовой формат и обязательная проверка контрольных цифр. Однообразные номера исключаются. Для настроенного шаблона документа дополнительно используются реквизиты бланка.",
        "Текст письма и вложений; шаблон документа — при наличии эталона."
    ],
    "RU_SNILS": [
        "Проверяется формат и контрольная сумма. При неверной сумме требуется явный локальный контекст СНИЛС, результат считается предполагаемым. Нулевые номера исключаются.",
        "Текст письма и вложений; шаблон документа — при наличии эталона."
    ],
    "RU_PASSPORT": [
        "Серия и номер проверяются вместе с паспортным контекстом в том же локальном блоке. Для зарегистрированного эталона возможна дополнительная проверка реквизитов бланка.",
        "Текст письма и вложений; шаблон документа — при наличии эталона."
    ],
    "SECRET": [
        "Текстовый шаблон либо сигнатура Gitleaks. Совпадения не проверяются обращением к внешним сервисам.",
        "Извлечённый текст и содержимое вложений, передаваемое Gitleaks."
    ],
    "PRIVATE_KEY": [
        "Распознавание заголовков закрытых ключей, без проверки содержимого ключа.",
        "Извлечённый текст."
    ],
    "CONFIDENTIAL": [
        "Достаточно одного из обозначений конфиденциальности в статическом шаблоне.",
        "Извлечённый текст."
    ],
    "PROMPT_INJECTION": [
        "Достаточно одного из альтернативных статических признаков: попытка отменить предыдущие инструкции или отключить анализ. Семантической интерпретации намерения нет.",
        "Извлечённый текст письма и вложений."
    ],
    "CODE": [
        "Распознавание характерных конструкций исходного кода, SQL или сценариев. Дополнительный локальный контекст конфиденциальности и передачи повышает риск.",
        "Извлечённый текст."
    ],
    "SUSPICIOUS_COMMAND": [
        "Статические признаки потенциально опасных команд; команды не выполняются.",
        "Извлечённый текст."
    ],
    "YARA": [
        "Любая совпавшая встроенная сигнатура формирует находку.",
        "Байты вложений."
    ],
    "OFFICE_MACRO": [
        "При наличии VBA-макросов учитываются результаты анализа типов AutoExec, Suspicious и IOC.",
        "Поддерживаемые форматы вложений Office."
    ],
    "MALWARE": [
        "ClamAV возвращает FOUND и имя совпавшей сигнатуры.",
        "Вложения, переданные антивирусу."
    ],
    "REFERENCE_DOCUMENT": [
        "Точное совпадение нормализованного отпечатка либо покрытие эталона не менее 30% и не менее трёх совпадающих фрагментов.",
        "Извлечённый текст при наличии зарегистрированных эталонов."
    ],
    "SEMANTIC_REFERENCE": [
        "Косинусное сходство не ниже настроенного порога; сохраняется лучшее совпадение для каждого документа и эталона.",
        "Тело письма и извлечённый текст вложений по отдельности."
    ]
}

def builtin_help(category_id):
    from app.category_catalog import LEGACY_ALIASES
    from app.detectors import TEXT_RULES, VERSION
    from app.document_templates import TEMPLATES
    from app import snils, passport

    key = LEGACY_ALIASES.get(category_id, category_id)
    if key not in BUILTIN_HELP:
        return None
    result = dict(BUILTIN_HELP[key])
    result["logic"], result["scope"] = DETAILS[key]
    result["rules"] = [
        {"id": category.lower(), "kind": "Regex", "risk": risk, "version": VERSION,
         "pattern": pattern, "flags": "Без учёта регистра" if pattern.startswith("(?i)") else
         "Многострочный режим" if pattern.startswith("(?m)") else "Стандартный режим"}
        for category, pattern, risk in TEXT_RULES if category == key
    ]
    if key in {"RU_SNILS", "RU_PASSPORT"}:
        # Use the actual compiled expressions rather than maintaining copies.
        patterns = [("Формат", snils._CANDIDATE), ("Контекст", snils._CONTEXT)] if key == "RU_SNILS" else [
            ("Серия и номер", passport._FIELDS), ("Табличный формат", passport._TABLE),
            ("Паспортный контекст", passport._CONTEXT)]
        result["rules"].extend({"id": label, "kind": "Regex", "pattern": pattern.pattern,
                                "flags": "Без учёта регистра" if pattern.flags & 2 else "Стандартный режим"}
                               for label, pattern in patterns)
    result["templates"] = [
        {"id": name, "label": spec["label"], "anchors": spec["anchors"],
         "minimum": spec["min_anchors"]}
        for name, spec in TEMPLATES.items()
        if LEGACY_ALIASES.get(spec["category"], spec["category"]) == key
    ]
    if key == "SEMANTIC_REFERENCE":
        from pipeline.semantic_detection import threshold, RISK
        from pipeline.inference import enabled
        result["risk"] = str(RISK) + " — вероятностный признак"
        try:
            result["logic"] += f" Порог развёртывания: {threshold():.2f}."
        except ValueError:
            result["logic"] += " Некорректная настройка порога."
        result["logic"] += " Автоматический анализ разрешён конфигурацией развёртывания." if enabled("semantic") else " Автоматический анализ выключен конфигурацией развёртывания."
    if key == "YARA":
        import re
        from app.advanced_detectors import YARA_SOURCE
        result["signatures"] = re.findall(r"(?m)^rule\s+(\w+)\s*\{", YARA_SOURCE)
    if key in {"SECRET", "MALWARE", "OFFICE_MACRO"}:
        result["external_note"] = (
            "Полный список внешних сигнатур не доступен через текущий интерфейс сканера. "
            "Идентификаторы фактических совпадений доступны в результатах анализа, если движок их возвращает. "
            "Список не имитируется и не загружается при открытии окна."
        )
    return result
