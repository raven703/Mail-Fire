# MICE: фактическое качество на benchmark-300-v2

Дата: 2026-11-20. Runtime backend: f66caec (API/worker), остальные backend: 7a0592f. Dataset branch: test/benchmark-300-v2-ground-truth.

## Методика и ограничения
300 писем импортированы штатным POST /api/import: пилот 5 и оставшиеся пакеты до 50. Ground Truth: expected_semantic_categories из manifest.jsonl. Разметка авторская синтетическая, без независимого экспертного ревью. Никакой подгонки и обучения. Категории сравниваются по точным ID без скрытого переименования. Все неожиданные категории включены в FP строгого сравнения; это не означает, что каждая дополнительная находка семантически неверна.
Активных ML-моделей нет. Поэтому качество ML-классификатора и ошибки именно ML не оценены; модели не включались. OCR, сканы, изображения, антивирусные сигнатуры, YARA и зашифрованные архивы отсутствуют в наборе: NOT TESTED.
Прежние 250 писем и 146 инцидентов удалены по явному указанию пользователя после резервной копии. Политики, категории, настройки, модели и обучающие примеры сохранены. Идентификаторы Docker/проекта остаются mailfire для совместимости.

## Общие показатели
```json
{
  "input_count": 300,
  "observed": 300,
  "statuses": {
    "ANALYZED": 300
  },
  "micro_all_categories": {
    "TP": 197,
    "FP": 54,
    "FN": 63,
    "TN": 8986,
    "precision": 0.7848605577689243,
    "recall": 0.7576923076923077,
    "F1": 0.7710371819960861
  },
  "exact_messages": 202,
  "incidents": 212,
  "processing_errors": 0,
  "attachment_errors": [],
  "ground_truth": "Author-defined synthetic semantic holdout, not expert-reviewed. Unexpected auxiliary categories count as strict FP, not confirmed semantic false alarms.",
  "runtime_models": "No active models at baseline; no training or activation performed.",
  "timing": {
    "complete": true,
    "elapsed_seconds": 1651.7800039180001
  },
  "messages_per_minute": 10.8973349703376
}
```

## По категориям / стабильным детекторам
TP/FP/FN — на уровне наличия категории в письме, не количества совпадений. Отдельную точность regex/Presidio по одному и тому же классу невозможно независимо оценить: GT не размечает источники находок. Исходные rule_id/source сохранены в results.csv.
|Категория|TP|FP|FN|TN|Precision|Recall|F1|Покрытие|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|CODE|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|CONFIDENTIAL|0|5|0|295|0.0000|N/A|0.0000|NO_POSITIVE_GROUND_TRUTH|
|EMAIL|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|INN|0|12|0|288|0.0000|N/A|0.0000|NO_POSITIVE_GROUND_TRUTH|
|MALWARE|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|NORMAL|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|OFFICE_MACRO|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|PHONE|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|PRIVATE_KEY|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|PROMPT_INJECTION|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|REFERENCE_DOCUMENT|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|RU_INN|5|7|9|279|0.4167|0.3571|0.3846|TESTED|
|RU_PASSPORT|0|0|14|286|N/A|0.0000|0.0000|TESTED|
|RU_PHONE|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|RU_SNILS|0|7|14|279|0.0000|0.0000|0.0000|TESTED|
|SECRET|10|7|0|283|0.5882|1.0000|0.7407|TESTED|
|SEMANTIC_REFERENCE|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|SUSPICIOUS_COMMAND|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|YARA|0|0|0|300|N/A|N/A|N/A|NO_POSITIVE_GROUND_TRUTH|
|pack-ru2-credential-transfer|15|0|0|285|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-customer-data|10|0|8|282|1.0000|0.5556|0.7143|TESTED|
|pack-ru2-data-exfil|17|0|0|283|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-explosive-threat|12|8|0|280|0.6000|1.0000|0.7500|TESTED|
|pack-ru2-extortion|11|0|0|289|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-financial-plans|32|0|0|268|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-internal-docs|16|0|0|284|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-phishing|20|8|0|272|0.7143|1.0000|0.8333|TESTED|
|pack-ru2-pii-handling|18|0|0|282|1.0000|1.0000|1.0000|TESTED|
|pack-ru2-pricing|11|0|16|273|1.0000|0.4074|0.5789|TESTED|
|pack-ru2-sabotage|9|0|2|289|1.0000|0.8182|0.9000|TESTED|
|pack-ru2-violence-threat|11|0|0|289|1.0000|1.0000|1.0000|TESTED|

## Разрез: group
|Значение|Писем|Точных|TP|FP|FN|Precision|Recall|F1|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|commercial|55|44|44|0|11|1.0000|0.8000|0.8889|
|control|60|30|0|44|0|0.0000|N/A|0.0000|
|documents|25|22|22|0|3|1.0000|0.8800|0.9362|
|mixed|20|10|30|5|10|0.8571|0.7500|0.8000|
|pii|55|13|18|5|37|0.7826|0.3273|0.4615|
|safety|45|43|43|0|2|1.0000|0.9556|0.9773|
|secrets|40|40|40|0|0|1.0000|1.0000|1.0000|

## Разрез: difficulty
|Значение|Писем|Точных|TP|FP|FN|Precision|Recall|F1|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|easy|91|68|63|15|14|0.8077|0.8182|0.8129|
|hard|118|67|68|22|37|0.7556|0.6476|0.6974|
|medium|91|67|66|17|12|0.7952|0.8462|0.8199|

## Разрез: attachment_type
|Значение|Писем|Точных|TP|FP|FN|Precision|Recall|F1|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|csv|48|38|42|1|10|0.9767|0.8077|0.8842|
|docx|48|38|43|2|9|0.9556|0.8269|0.8866|
|html|48|37|42|2|10|0.9545|0.8077|0.8750|
|none|84|45|16|44|10|0.2667|0.6154|0.3721|
|txt|24|17|22|3|4|0.8800|0.8462|0.8627|
|xlsx|48|27|32|2|20|0.9412|0.6154|0.7442|

## Разрез: scenario
|Значение|Писем|Точных|TP|FP|FN|Precision|Recall|F1|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|cost_margin|11|11|11|0|0|1.0000|1.0000|1.0000|
|credential_transfer|10|10|10|0|0|1.0000|1.0000|1.0000|
|customer_database_export|13|10|10|0|3|1.0000|0.7692|0.8696|
|document_exfiltration|12|12|12|0|0|1.0000|1.0000|1.0000|
|dummy_number|7|0|0|21|0|0.0000|N/A|0.0000|
|explosive_threat|12|12|12|0|0|1.0000|1.0000|1.0000|
|extortion|11|11|11|0|0|1.0000|1.0000|1.0000|
|fake_credential_training|7|0|0|7|0|0.0000|N/A|0.0000|
|fictional_threat_quote|8|0|0|8|0|0.0000|N/A|0.0000|
|financial_forecast|11|11|11|0|0|1.0000|1.0000|1.0000|
|inn_certificate|14|0|5|5|9|0.5000|0.3571|0.4167|
|internal_budget|11|11|11|0|0|1.0000|1.0000|1.0000|
|it_sabotage|11|9|9|0|2|1.0000|0.8182|0.9000|
|mixed_customer_price|5|0|0|0|10|N/A|0.0000|0.0000|
|mixed_exfil_internal|5|0|10|5|0|0.6667|1.0000|0.8000|
|mixed_finance_pii|5|5|10|0|0|1.0000|1.0000|1.0000|
|mixed_forecast_credentials|5|5|10|0|0|1.0000|1.0000|1.0000|
|normal_invoice|7|7|0|0|0|N/A|N/A|N/A|
|passport_russian|14|0|0|0|14|N/A|0.0000|0.0000|
|phishing_account|10|10|10|0|0|1.0000|1.0000|1.0000|
|phishing_otp|10|10|10|0|0|1.0000|1.0000|1.0000|
|phishing_training|8|0|0|8|0|0.0000|N/A|0.0000|
|pii_transfer|13|13|13|0|0|1.0000|1.0000|1.0000|
|policy_discussion|7|7|0|0|0|N/A|N/A|N/A|
|public_budget|8|8|0|0|0|N/A|N/A|N/A|
|public_pricing|8|8|0|0|0|N/A|N/A|N/A|
|restricted_doc|11|11|11|0|0|1.0000|1.0000|1.0000|
|restricted_pricing|11|0|0|0|11|N/A|0.0000|0.0000|
|secret_leak|10|10|10|0|0|1.0000|1.0000|1.0000|
|snils_card|14|0|0|0|14|N/A|0.0000|0.0000|
|violence_threat|11|11|11|0|0|1.0000|1.0000|1.0000|

## Проблемные письма
|Файл|Сценарий|FP относительно GT|FN|Статус|
|---|---|---|---|---|
|eml/MF300-0002.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0003.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0006.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0008.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0010.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0011.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0014.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0016.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0018.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0019.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0022.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0024.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0026.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0027.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0030.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0032.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0034.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0035.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0038.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0040.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0042.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0043.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0046.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0048.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0050.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0051.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0054.eml|dummy_number|INN;RU_INN;RU_SNILS||ANALYZED|
|eml/MF300-0056.eml|fake_credential_training|SECRET||ANALYZED|
|eml/MF300-0058.eml|phishing_training|pack-ru2-phishing||ANALYZED|
|eml/MF300-0059.eml|fictional_threat_quote|pack-ru2-explosive-threat||ANALYZED|
|eml/MF300-0061.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0062.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0063.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0065.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0066.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0067.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0069.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0070.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0071.eml|inn_certificate|INN||ANALYZED|
|eml/MF300-0073.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0074.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0075.eml|inn_certificate|INN||ANALYZED|
|eml/MF300-0077.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0078.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0079.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0081.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0082.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0083.eml|inn_certificate|INN||ANALYZED|
|eml/MF300-0085.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0086.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0087.eml|inn_certificate|INN||ANALYZED|
|eml/MF300-0089.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0090.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0091.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0093.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0094.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0095.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0097.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0098.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0099.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0101.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0102.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0103.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0105.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0106.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0107.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0109.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0110.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0111.eml|inn_certificate|INN||ANALYZED|
|eml/MF300-0113.eml|passport_russian||RU_PASSPORT|ANALYZED|
|eml/MF300-0114.eml|snils_card||RU_SNILS|ANALYZED|
|eml/MF300-0115.eml|inn_certificate||RU_INN|ANALYZED|
|eml/MF300-0118.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0123.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0128.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0133.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0138.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0143.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0148.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0153.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0158.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0163.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0168.eml|restricted_pricing||pack-ru2-pricing|ANALYZED|
|eml/MF300-0186.eml|it_sabotage||pack-ru2-sabotage|ANALYZED|
|eml/MF300-0206.eml|it_sabotage||pack-ru2-sabotage|ANALYZED|
|eml/MF300-0256.eml|customer_database_export||pack-ru2-customer-data|ANALYZED|
|eml/MF300-0266.eml|customer_database_export||pack-ru2-customer-data|ANALYZED|
|eml/MF300-0276.eml|customer_database_export||pack-ru2-customer-data|ANALYZED|
|eml/MF300-0282.eml|mixed_customer_price||pack-ru2-customer-data;pack-ru2-pricing|ANALYZED|
|eml/MF300-0283.eml|mixed_exfil_internal|CONFIDENTIAL||ANALYZED|
|eml/MF300-0286.eml|mixed_customer_price||pack-ru2-customer-data;pack-ru2-pricing|ANALYZED|
|eml/MF300-0287.eml|mixed_exfil_internal|CONFIDENTIAL||ANALYZED|
|eml/MF300-0290.eml|mixed_customer_price||pack-ru2-customer-data;pack-ru2-pricing|ANALYZED|
|eml/MF300-0291.eml|mixed_exfil_internal|CONFIDENTIAL||ANALYZED|
|eml/MF300-0294.eml|mixed_customer_price||pack-ru2-customer-data;pack-ru2-pricing|ANALYZED|
|eml/MF300-0295.eml|mixed_exfil_internal|CONFIDENTIAL||ANALYZED|
|eml/MF300-0298.eml|mixed_customer_price||pack-ru2-customer-data;pack-ru2-pricing|ANALYZED|
|eml/MF300-0299.eml|mixed_exfil_internal|CONFIDENTIAL||ANALYZED|

## Приоритеты улучшения (не реализованы)
1. P1: разобрать FN по категориям и сценариям из таблиц; отделить отсутствие словарного покрытия от классификационных ошибок. Не обучать на holdout.
2. P1: проверить FP на отрицательных контролях: цитаты угроз, учебные примеры фишинга, публичные прайсы и тестовые реквизиты требуют контекста/ручного ревью.
3. P2: согласовать семантическую онтологию benchmark с вспомогательными EMAIL/PHONE/INN/CONFIDENTIAL; публиковать строгую метрику отдельно от контекстной экспертной оценки.
4. P2: выполнить отдельный OCR/AV benchmark с контролируемыми сканами/PDF и бинарными образцами: данный набор таких выводов не позволяет.
5. P2: оценить ML на отдельной опубликованной модели и независимой выборке только после согласования; отсутствие активной модели не считать успешной ML-проверкой.
6. P3: измерить нагрузочный параллельный импорт отдельно; данный прогон характеризует текущую очередь и конфигурацию, не максимальную пропускную способность.

Найденные несовпадения не исправлялись. Все находки, evidence, errors и проблемные письма сохранены в CSV.

## Проверка сохранности и очередей
Снимки policies, categories, category_rules, settings, ml_models (хеши артефактов), training_examples, ml_datasets, references полностью совпадают до очистки и после прогона. Обучение не запускалось. Очередь: analyze DONE=300, evaluate DONE=300; незавершённых заданий тестового прогона нет. Исторический ml_train DONE=1 сохранён. Все 216 вложений имеют ANALYZED, ошибок движков нет. Общее время включает импорт и ожидание очереди, скорость около 10.90 писем/мин; latency отдельных писем не измерялась. Создано 212 инцидентов; это не TP угроз и не независимая метрика качества детектора.

## Разбор расхождений
- RU_PASSPORT: 14 FN из 14. В примере MF300-0061 сведения передаются во вложении: требуется разбор извлечённого текста и формата реквизитов. Это не OCR-ошибка, поскольку в наборе нет сканов.
- RU_SNILS: 14 FN из 14 и 7 дополнительных срабатываний. MF300-0062 содержит `100080947-00`: формат отличается от поддерживаемой группировки номера. Контрольная сумма и семантическая разметка также требуют проверки. Это гипотеза причины, не исправление.
- RU_INN: 9 FN и 7 FP; INN даёт ещё 12 дополнительных находок относительно семантического GT. Наличие намеренно невалидных идентификаторов и проверок контрольной суммы означает, что семантическое намерение автора и распознавание валидного реквизита могут расходиться.
- pack-ru2-pricing: 16 FN; pack-ru2-customer-data: 8 FN; sabotage: 2 FN. Требуется экспертный просмотр формулировок и словарного покрытия, без расширения правил на данном holdout.
- Дополнительные срабатывания explosive-threat=8 и phishing=8: проверить цитаты, учебные примеры и отрицательные контроли прежде чем считать все 16 реальными ложными тревогами.
- SECRET=7 дополнительных срабатываний и CONFIDENTIAL=5 требуют контекстной оценки; семантический GT не является точной спецификацией статических сигнатур.
- Ошибки ML-классификации не установлены: активных ML-моделей нет. Ошибки OCR не оценены: OCR-примеров нет. Эти ограничения не следует интерпретировать как нулевую частоту ошибок соответствующих подсистем.

## Исходные материалы
Набор и исходная разметка: test-data/benchmark-300-v2 (получены из ветки test/benchmark-300-v2-ground-truth без изменения меток). По каждому письму results.csv содержит ожидаемые/фактические категории, FN/FP, исходные findings, rule_id, source и результаты извлечения. input-hashes.json фиксирует входные EML. Локальные резервные копии БД и секреты в Git не включены.
