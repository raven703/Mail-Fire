# Mail-Fire E2E: все 250 EML

> **СТАТУС ПРОГОНА: INVALID_FOR_FROZEN_CONFIGURATION.** Во время обработки внешним действием выключена существующая политика «Высокий риск — проверка аналитиком» (версия 3 → 4), добавлена настройка detectors.antivirus=false. Категории, словари и E2E-политики не изменились. Метрики ниже — наблюдаемые результаты, НЕ подтверждение успешного неизменного E2E-прогона. Количества инцидентов зависят от момента изменения политики. Автоматического восстановления или повторного прогона не выполнялось.


Начало: run-20261119T170326
Артефакты: `/home/user/.local/share/mailfire/e2e/run-20261119T170326`

Импорт: 250/250; новых сообщений: 244; существующих: 6.
Обработка завершена: True; ошибки обработки: 0.
Статусы: {'PARTIAL': 250}.
Точное совпадение категорий: 250/250. Новых инцидентов: 471.

## Методика
Метрики one-vs-rest по каждой категории. Ошибки обработки исключены из confusion matrix и учтены отдельно. Микроагрегация — только категории с положительными ожиданиями в manifest. Все неожиданные категории сохранены в CSV. NOT TESTED означает отсутствие положительных примеров, а не успешный тест.
Детекторы пакета нормализованы из UUID правила в стабильный ID категории; исходные UUID и источники сохранены в CSV. TN — отсутствие категории в ожиданиях и находках.

## Общая статистика
{"TP": 303, "FP": 0, "FN": 0, "TN": 2197, "precision": 1.0, "recall": 1.0, "F1": 1.0}

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
|custom-2e37f6e513fe42c0a527570839c17f9b|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|custom-5b4a5cb3872e48adabf093ca53d2c72b|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|custom-da6b62890d0a44e4a00279e28222a574|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-credentials-requests-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-finance-plans-ru|TESTED|35|0|0|215|1.0000|1.0000|1.0000|
|pack-internal-materials-ru|TESTED|21|0|0|229|1.0000|1.0000|1.0000|
|pack-phishing-requests-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-threat-explosives-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-threat-extortion-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-threat-sabotage-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|
|pack-threat-violence-ru|NOT TESTED|0|0|0|250|N/A|N/A|N/A|

## Вложения
|Формат|Вложений|Извлечено|Ошибок|Писем|Точное совпадение категорий|FN|FP|
|---|---:|---:|---:|---:|---:|---:|---:|
|TXT|52|52|0|52|52|0|0|
|DOCX|73|73|0|73|73|0|0|
|XLSX|58|58|0|58|58|0|0|

## Ограничения
- PARTIAL with no extraction/ML/job errors is included in detection metrics; ClamAV disabled, antivirus NOT TESTED.
- Categories without positive manifest examples are NOT TESTED; their unexpected findings are still reported as FP.
- Attachment format detection metrics are message-level; findings do not reliably attribute individual attachments.
- Manifest expects rule behavior, including confidential keyword in contextual negative controls; not a semantic ground truth.
- No rule/code changes during run; existing results are identified separately.

## Несовпадения по письмам
|Файл|Статус|FN|FP|Ошибки|
|---|---|---|---|---|

## Дедупликация и детекторы
244 новых сообщения и 6 ранее существовавших: существующие не засчитаны как новые. Все 250 оригиналов повторно поданы API, исходные EML не изменены. Новые сообщения: точное совпадение категорий 244/244. Существующие: 6/6; это не новые результаты анализа.
{"exact_matches": 250, "FN": 0, "FP": 0}

## Метрики обнаружения по форматам (на уровне письма)
- TXT: {"TP": 59, "FP": 0, "FN": 0, "precision": 1.0, "recall": 1.0, "F1": 1.0}
- DOCX: {"TP": 89, "FP": 0, "FN": 0, "precision": 1.0, "recall": 1.0, "F1": 1.0}
- XLSX: {"TP": 87, "FP": 0, "FN": 0, "precision": 1.0, "recall": 1.0, "F1": 1.0}

## Конфигурация и сохранённые данные
Перед импортом добавлены 30 отдельных E2E250-политик для активных категорий (min_risk=0, min_count=1, shadow=false, без фильтров). Существующие политики и словари данным тестовым скриптом не редактировались. E2E-политики, импортированные сообщения и инциденты оставлены в БД; обратных изменений не выполнялось.
