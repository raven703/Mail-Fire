# Mail-Fire E2E: все 250 EML

Начало: 2026-11-20T08:56:44.509035+00:00
Артефакты: `/home/user/.local/share/mailfire/e2e/run-20261120T115644`

Импорт: 250/250; новых сообщений: 250; существующих: 0.
Обработка завершена: True; ошибки обработки: 0.
Статусы: {'PARTIAL': 250}.
Точное совпадение категорий: 194/250. Новых инцидентов: 146.

## Методика
Метрики one-vs-rest по каждой категории. Ошибки обработки исключены из confusion matrix и учтены отдельно. Микроагрегация — только категории с положительными ожиданиями в manifest. Все неожиданные категории сохранены в CSV. NOT TESTED означает отсутствие положительных примеров, а не успешный тест.
Детекторы пакета нормализованы из UUID правила в стабильный ID категории; исходные UUID и источники сохранены в CSV. TN — отсутствие категории в ожиданиях и находках.

## Общая статистика
{"TP": 275, "FP": 0, "FN": 28, "TN": 2197, "precision": 1.0, "recall": 0.9075907590759076, "F1": 0.9515570934256056}

## По категориям
|Категория|Статус|TP|FP|FN|TN|Precision|Recall|F1|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|CODE|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|CONFIDENTIAL|TESTED|35|0|0|215|1.0000|1.0000|1.0000|
|EMAIL|TESTED|46|0|0|204|1.0000|1.0000|1.0000|
|INN|TESTED|23|0|0|227|1.0000|1.0000|1.0000|
|MALWARE|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|NORMAL|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|OFFICE_MACRO|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|PHONE|TESTED|46|0|0|204|1.0000|1.0000|1.0000|
|PRIVATE_KEY|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|PROMPT_INJECTION|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|REFERENCE_DOCUMENT|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|RU_INN|TESTED|23|0|0|227|1.0000|1.0000|1.0000|
|RU_PASSPORT|TESTED|21|0|0|229|1.0000|1.0000|1.0000|
|RU_PHONE|TESTED|46|0|0|204|1.0000|1.0000|1.0000|
|RU_SNILS|TESTED|7|0|0|243|1.0000|1.0000|1.0000|
|SECRET|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|SEMANTIC_REFERENCE|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|SUSPICIOUS_COMMAND|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|YARA|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-credential-transfer|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-customer-data|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-data-exfil|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-explosive-threat|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-extortion|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-financial-plans|TESTED|14|0|21|215|1.0000|0.4000|0.5714|
|pack-ru2-internal-docs|TESTED|14|0|7|229|1.0000|0.6667|0.8000|
|pack-ru2-phishing|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-pii-handling|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-pricing|NOT TESTED|0|35|0|215|0.0000|N/A|0.0000|
|pack-ru2-sabotage|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-ru2-violence-threat|NOT TESTED|0|0|0|250|N/A|N/A|N/A|

## Вложения
|Формат|Вложений|Извлечено|Ошибок|Писем|Точное совпадение категорий|FN|FP|
|---|---:|---:|---:|---:|---:|---:|---:|
|TXT|52|52|0|52|31|14|14|
|DOCX|73|73|0|73|59|7|7|
|XLSX|58|58|0|58|37|7|14|

## Ограничения
- PARTIAL with no extraction/ML/job errors is included in detection metrics; ClamAV disabled, antivirus NOT TESTED.
- Categories without positive manifest examples are NOT TESTED; their unexpected findings are still reported as FP.
- Attachment format detection metrics are message-level; findings do not reliably attribute individual attachments.
- Manifest expects rule behavior, including confidential keyword in contextual negative controls; not a semantic ground truth.
- No rule/code changes during run; existing results are identified separately.

## Несовпадения по письмам
|Файл|Статус|FN|FP|Ошибки|
|---|---|---|---|---|
|eml/019-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/021-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/024-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/027-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/028-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/029-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/030-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/034-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/053-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/055-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/058-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/061-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/062-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/063-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/064-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/068-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/087-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/089-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/092-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/095-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/096-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/097-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/098-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/102-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/121-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/123-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/126-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/129-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/130-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/131-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/132-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/136-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/155-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/157-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/160-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/163-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/164-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/165-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/166-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/170-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/189-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/191-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/194-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/197-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/198-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/199-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/200-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/204-control.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/223-commercial.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/225-commercial.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/228-commercial.eml|PARTIAL|pack-ru2-financial-plans|pack-ru2-pricing|[]|
|eml/231-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/232-mixed.eml|PARTIAL||pack-ru2-pricing|[]|
|eml/233-mixed.eml|PARTIAL|pack-ru2-internal-docs||[]|
|eml/234-mixed.eml|PARTIAL|pack-ru2-financial-plans||[]|
|eml/238-control.eml|PARTIAL||pack-ru2-pricing|[]|

## Итоговая независимая проверка

{
  "configuration_unchanged": true,
  "all_categories_micro_vs_manifest": {
    "TP": 275,
    "FP": 35,
    "FN": 28,
    "precision": 0.8870967741935484,
    "recall": 0.9075907590759076,
    "F1": 0.8972267536704731
  },
  "incident_execution_vs_actual_findings": {
    "TP": 146,
    "TN": 104
  },
  "exact_policy_sets": 250,
  "policy_hits": {
    "Prompt Injection": 0,
    "Вредоносное содержимое": 0,
    "Исходный код и внутренние документы": 0,
    "Коммерческая тайна": 56,
    "Пароли и секреты": 0,
    "Персональные данные": 97,
    "Угрозы безопасности": 0,
    "Фишинг и социальная инженерия": 0
  },
  "note": "Incident metrics validate execution against actual findings and configured thresholds, not independent semantic ground truth. Pricing FP means unexpected by manifest."
}

Сопоставление ID: pack-finance-plans-ru → pack-ru2-financial-plans; pack-internal-materials-ru → pack-ru2-internal-docs. Это сопоставление назначения категорий, а не гарантия эквивалентности словарей.
Время импорта и ожидания очереди: 1485.26 с (24 мин 45 с), 10.10 писем/мин. Per-message latency не измерялась.
