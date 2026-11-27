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
        "method": "В каталоге заявлены Multilingual MiniLM / pgvector. В проверенном текущем конвейере отдельное формирование находок этой категории не подтверждено.",
        "risk": "Не подтверждён",
        "limitations": "Наличие категории в каталоге не означает, что соответствующий механизм выполняется.",
        "source": "app/detector_catalog.py; app/detection_evidence.py; pipeline/inference.py"
    }
}

def builtin_help(category_id):
    from app.category_catalog import LEGACY_ALIASES
    return BUILTIN_HELP.get(LEGACY_ALIASES.get(category_id, category_id))
