"""Legacy detector catalog without importing HTTP, ORM or inference engines."""

DETECTORS = {
    "pii": (
        "Персональные данные",
        "Presidio: российские ПДн, контрольные суммы ИНН/СНИЛС",
        ["EMAIL", "PHONE", "INN", "RU_SNILS", "RU_PASSPORT"],
    ),
    "static_files": (
        "Статический анализ вложений",
        "YARA и oletools; без исполнения кода",
        ["YARA", "OFFICE_MACRO"],
    ),
    "antivirus": ("Антивирус", "ClamAV INSTREAM; требует включённого сервиса", ["MALWARE"]),
    "secrets": ("Секреты и ключи", "Статические сигнатуры", ["SECRET", "PRIVATE_KEY"]),
    "confidential": ("Грифы конфиденциальности", "Статические текстовые сигнатуры", ["CONFIDENTIAL"]),
    "code": ("Исходный код и команды", "Статические эвристики", ["CODE", "SUSPICIOUS_COMMAND"]),
    "prompt": ("Prompt injection", "Контекстные эвристики", ["PROMPT_INJECTION"]),
    "reference": ("Эталонные документы", "Fingerprint / MinHash", ["REFERENCE_DOCUMENT"]),
    "semantic": ("Семантическое сходство", "Multilingual MiniLM / pgvector", ["SEMANTIC_REFERENCE"]),
    "ml": ("ML-классификатор", "TF-IDF / SetFit / RuBERT", []),
    "horizon": ("Horizon Zero-shot", "Локальная NLI-модель · CPU / опциональный CUDA · выключен по умолчанию", []),
    "normalizer": ("Нормализация текста", "Детерминированный поиск с координатами оригинала", []),
}
