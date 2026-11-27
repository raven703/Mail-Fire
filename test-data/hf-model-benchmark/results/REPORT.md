# Независимый GPU-бенчмарк Hugging Face / B-350

## Условия и статус

Дата: 27 ноября 2026. Ничего не обучалось; рабочий MICE и исходные EML/manifest не изменены.
Отдельное venv, CUDA RTX 4060; только FP32, FP16 не использовался. Модели выполнялись последовательно в отдельных процессах.
Ревизии, лицензии, labels, версии и GPU: `environment.json`, `model_audit.json`.
Протокол, все 350 ID и hashes зафиксированы отдельным коммитом до инференса.

| Модель | Статус | Лицензия |
|---|---|---|
| Horizon-Labs/multilingual-zeroshot-base | completed | apache-2.0 |
| MoritzLaurer/mDeBERTa-v3-base-mnli-xnli | completed | mit |
| redmadrobot-rnd/rubert-base-pii-ner | completed | apache-2.0 |
| ScienceSoft/scnsoft-pii-encoder | blocked_gpu | other |
| Gloomreach/ru-toxicity-encoder | completed | mit |
| Aleksandr505/phishing-text-classifier-rubert | completed | unspecified |

## Методика и ограничения

- Все 350 писем классифицируются одинаковым текстом: subject, MIME body и доступные вложения. Контроли, учебные примеры, цитаты и пересылки не исключаются.
- DOCX/XLSX извлечены непосредственно из ZIP/XML; HTML очищен; TXT/CSV декодированы; PDF через pypdf. Manifest используется только как ground truth, не как источник текста вложений.
- OCR Tesseract отсутствует: 6 PNG-вложений не распознаны. Письма остаются в полном прогоне; ошибки помечены extraction_limited. Есть дополнительные метрики на extraction-complete subset. Это не доказывает, что каждую ошибку вызвал OCR.
- Window 900 символов, overlap 100; максимум 512 токенов. Максимум вероятности по окнам усиливает как recall, так и FP. Сохраняются logits, полные классовые вероятности, усечения и provenance.
- NLI: одинаковые английские гипотезы, independent entailment-vs-contradiction softmax (neutral mDeBERTa не входит в знаменатель). Порог 0.5 до smoke. Нормализации между категориями нет, safe может пересекаться с другими ответами.
- Семантические категории — фиксированные proxies из protocol.json: коммерция=pricing, финансы=financial-plans; exfiltration включает SECRET/credentials. Они не охватывают все возможные значения понятий. Safe оценивается по авторскому expected_no_issue.
- Phishing: softmax Phishing=0, Legit=1, threshold 0.5. Gloomreach: три sigmoid головы; только threat сопоставляется с violence/explosive, threshold 0.4 из upstream config; profanity/illegal без gold не оцениваются.
- B-350 не содержит эталонных entity spans: NER на B-350 только качественный, без TP/FP/FN. Нет требования находить организации моделью redmadrobot, где такого класса нет.
- Малый отдельный NER fixture с вручную указанными в файле spans создан AI, а не независимым человеком. Его exact-span метрики — только проверка механики, не независимое качество. Требуется человеческая проверка границ и более широкий корпус, включая адреса/организации согласно поддерживаемым классам.
- ИНН/СНИЛС/паспорт остаются задачей алгоритмических детекторов. NER-метрики по ним не выставлялись.
- ScienceSoft: опубликован только int8 CPU-oriented ONNX; GPU/Transformers smoke и основной прогон не выполнялись, CPU fallback и конвертация весов запрещены протоколом. ONNX Runtime CUDA provider отдельно не исследовался: это ограничение данного запуска, а не доказательство невозможности любого GPU backend. Лицензия разрешает воспроизводить оценку, но не production/модификацию/redistribution.
- Gloomreach: локальная reviewed реализация опубликованной архитектуры, weights_only=True и strict=True для полного checkpoint. Никакой удалённый Python не исполнялся, случайных недостающих голов не допускается.
- Первый Gloomreach load остановился до smoke: checkpoint оказался обёрткой с model_state_dict/epoch/val_loss/class_weights, а не голым state_dict. Исправлен только reader обёртки; 61 ключ полного encoder/трёх голов проверены strict=True. Исходная ошибка сохранена в gloomreach-initial-load-error.json. Retry выполнен после завершения остальных GPU-процессов, протокол/пороги/веса не менялись.
- Aleksandr505: лицензия не указана; production требует отдельного правового согласования.
- B-350 синтетический, авторски размеченный. Это не доказательство производственной точности и не независимый человеческий NER benchmark.

## Классификация: полный B-350

Сравнивать только одинаковую категорию/выборку, не общий F1 NER и классификаторов.

| Модель | Категория | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| horizon | commercial | 3 | 0 | 27 | 1.000 | 0.100 | 0.182 |
| horizon | personal | 14 | 0 | 79 | 1.000 | 0.151 | 0.262 |
| horizon | financial | 33 | 6 | 3 | 0.846 | 0.917 | 0.880 |
| horizon | exfiltration | 4 | 1 | 44 | 0.800 | 0.083 | 0.151 |
| horizon | phishing | 21 | 20 | 2 | 0.512 | 0.913 | 0.656 |
| horizon | threat | 11 | 0 | 18 | 1.000 | 0.379 | 0.550 |
| horizon | safe | 0 | 0 | 70 | 0.000 | 0.000 | 0.000 |
| mdeberta | commercial | 8 | 65 | 22 | 0.110 | 0.267 | 0.155 |
| mdeberta | personal | 26 | 0 | 67 | 1.000 | 0.280 | 0.437 |
| mdeberta | financial | 18 | 5 | 18 | 0.783 | 0.500 | 0.610 |
| mdeberta | exfiltration | 32 | 174 | 16 | 0.155 | 0.667 | 0.252 |
| mdeberta | phishing | 16 | 147 | 7 | 0.098 | 0.696 | 0.172 |
| mdeberta | threat | 18 | 19 | 11 | 0.486 | 0.621 | 0.545 |
| mdeberta | safe | 0 | 0 | 70 | 0.000 | 0.000 | 0.000 |
| gloomreach | threat | 0 | 5 | 29 | 0.000 | 0.000 | 0.000 |
| phishing | phishing | 10 | 39 | 13 | 0.204 | 0.435 | 0.278 |

### Сопоставимые модели и практические рекомендации

- commercial: Horizon F1=0.182, FP=0, FN=27; mDeBERTa F1=0.155, FP=65, FN=22. Только эта категория и общий cohort сопоставимы.
- personal: Horizon F1=0.262, FP=0, FN=79; mDeBERTa F1=0.437, FP=0, FN=67. Только эта категория и общий cohort сопоставимы.
- financial: Horizon F1=0.880, FP=6, FN=3; mDeBERTa F1=0.610, FP=5, FN=18. Только эта категория и общий cohort сопоставимы.
- exfiltration: Horizon F1=0.151, FP=1, FN=44; mDeBERTa F1=0.252, FP=174, FN=16. Только эта категория и общий cohort сопоставимы.
- phishing: Horizon F1=0.656, FP=20, FN=2; mDeBERTa F1=0.172, FP=147, FN=7. Только эта категория и общий cohort сопоставимы.
- threat: Horizon F1=0.550, FP=0, FN=18; mDeBERTa F1=0.545, FP=19, FN=11. Только эта категория и общий cohort сопоставимы.
- safe: Horizon F1=0.000, FP=0, FN=70; mDeBERTa F1=0.000, FP=0, FN=70. Только эта категория и общий cohort сопоставимы.
- Профильный gloomreach/threat: F1=0.000, FP=5, FN=29; сравнивается только с NLI-строками threat.
- Профильный phishing/phishing: F1=0.278, FP=39, FN=13; сравнивается только с NLI-строками phishing.
- Gloomreach threat в этом протоколе не обнаружил ни одного положительного B-350 примера: не рекомендован как единственный threat detector. Это не оценка profanity/illegal и не доказательство качества вне данного домена. Upstream пример использует 128-token truncation; здесь заранее зафиксирована общая оконная схема 512 tokens, что также ограничивает перенос выводов.
- Специализированный phishing RuBERT уступил Horizon по phishing F1 на том же cohort и пороге, но превысил mDeBERTa при этих гипотезах. Нельзя переносить это на иные корпуса/лицензионные условия.

При данном фиксированном протоколе Horizon — кандидат для дальнейшей проверки financial, но не готовая универсальная DLP-модель. Высокая precision при низком recall на отдельных категориях не означает полноту защиты.
mDeBERTa в текущей формулировке phishing/exfiltration требует особенно тщательной проверки FP. Это результат конкретных гипотез/порога/корпуса, не доказательство общего превосходства архитектуры Horizon.
Обе NLI-модели могут не выбирать safe: это самостоятельная гипотеза, а не автоматическое отрицание остальных классов. Нулевой safe F1 при этом протоколе не означает, что все безопасные письма помечены опасными.
Redmadrobot можно рассматривать только как кандидат на entity extraction после человеческой span-разметки, не как DLP-policy classifier. ScienceSoft не подходит для запрошенного неизменённого PyTorch/CUDA запуска; production также не разрешён опубликованными условиями. Phishing-кандидат требует выяснения лицензии.

## NER: только отдельный AI-authored fixture

Не сравнивать эти exact-span показатели с document-level F1 B-350. Организации/адресные компоненты вне metric_scope не получают ложный нулевой F1.
| Тип | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| FIRST_NAME | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| LAST_NAME | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| MIDDLE_NAME | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| CITY | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| EMAIL | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PHONE | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |

## Источники

- [Horizon-Labs/multilingual-zeroshot-base](https://huggingface.co/Horizon-Labs/multilingual-zeroshot-base/blob/a9a5a24e58c794a0f7532d3de842236435a9ae22/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.
- [MoritzLaurer/mDeBERTa-v3-base-mnli-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli/blob/8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.
- [redmadrobot-rnd/rubert-base-pii-ner](https://huggingface.co/redmadrobot-rnd/rubert-base-pii-ner/blob/c802e8cd26f85d1cf920973ea6f83965a0618d63/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.
- [ScienceSoft/scnsoft-pii-encoder](https://huggingface.co/ScienceSoft/scnsoft-pii-encoder/blob/90f8317af633e751f2879cac264dcc6016eea048/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.
- [Gloomreach/ru-toxicity-encoder](https://huggingface.co/Gloomreach/ru-toxicity-encoder/blob/7f6078955e01b4cec3c89ff141fe8603137808c7/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.
- [Aleksandr505/phishing-text-classifier-rubert](https://huggingface.co/Aleksandr505/phishing-text-classifier-rubert/blob/c77cfad07a9f29cd0a7592eb189730427fc62313/README.md): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.

## Производительность

| Модель | Время основного прогона, с | Писем/с | Peak RAM GiB | Peak allocated VRAM GiB |
|---|---:|---:|---:|---:|
| horizon | 21.81 | 16.05 | 2.35 | 1.23 |
| mdeberta | 19.66 | 17.80 | 2.83 | 1.16 |
| redmadrobot | 3.35 | 104.33 | 1.66 | 0.67 |
| gloomreach | 1.40 | 250.78 | 1.38 | 0.12 |
| phishing | 3.02 | 115.82 | 1.75 | 0.67 |

RAM sampled 20ms; VRAM allocated/reserved — process PyTorch allocator, не desktop VRAM. Loading/download excluded from throughput; serialization/windowing included. NER timing includes small fixture. No cross-task speed ranking.

## Ошибки сложных контекстов

Полный errors.csv сохраняет ID, scenario, group, attachment type и признак extraction limitation. Ни один ошибочный пример не исключён.

- horizon/financial: public_budget, FP=5.
- horizon/phishing: phishing_training, FP=8.
- horizon/phishing: training_key, FP=1.
- horizon/safe: fake_credential_training, FN=7.
- horizon/safe: fake_number, FN=1.
- horizon/safe: fictional_quote, FN=1.
- horizon/safe: fictional_threat_quote, FN=8.
- horizon/safe: news_quote, FN=1.
- horizon/safe: phishing_training, FN=8.
- horizon/safe: policy_discussion, FN=7.
- horizon/safe: public_budget, FN=9.
- horizon/safe: public_event, FN=1.
- horizon/safe: public_offer, FN=1.
- horizon/safe: public_png, FN=1.
- horizon/safe: public_pricing, FN=8.
- horizon/safe: training_key, FN=1.
- mdeberta/exfiltration: fake_credential_training, FP=7.
- mdeberta/exfiltration: fake_number, FP=1.
- mdeberta/exfiltration: fictional_quote, FP=1.
- mdeberta/exfiltration: news_quote, FP=1.
- mdeberta/exfiltration: policy_discussion, FP=7.
- mdeberta/exfiltration: public_budget, FP=1.
- mdeberta/exfiltration: public_event, FP=1.
- mdeberta/exfiltration: public_png, FP=1.
- mdeberta/exfiltration: training_key, FP=1.
- mdeberta/phishing: fake_number, FP=1.
- mdeberta/phishing: training_key, FP=1.
- mdeberta/safe: fake_credential_training, FN=7.
- mdeberta/safe: fake_number, FN=1.
- mdeberta/safe: fictional_quote, FN=1.
- mdeberta/safe: fictional_threat_quote, FN=8.
- mdeberta/safe: news_quote, FN=1.
- mdeberta/safe: phishing_training, FN=8.
- mdeberta/safe: policy_discussion, FN=7.
- mdeberta/safe: public_budget, FN=9.
- mdeberta/safe: public_event, FN=1.
- mdeberta/safe: public_offer, FN=1.
- mdeberta/safe: public_png, FN=1.
- mdeberta/safe: public_pricing, FN=8.
- mdeberta/safe: training_key, FN=1.
- phishing/phishing: fake_number, FP=1.
- phishing/phishing: fictional_quote, FP=1.
- phishing/phishing: news_quote, FP=1.
- phishing/phishing: public_offer, FP=1.
- phishing/phishing: public_png, FP=1.
- phishing/phishing: training_key, FP=1.

## Выводы и дальнейшая проверка

Для сравнения Horizon и mDeBERTa используйте строки одной категории; для phishing/threat добавляйте профильную модель только в той же колонке. Универсальная суммарная оценка шести моделей намеренно отсутствует.
Ни одна модель не утверждается как production-ready. Кандидат на отдельную проверку должен показать приемлемый FP на независимой реальной/экспертно размеченной выборке и пройти анализ лицензии, latency, обфускации, длинных цепочек и вложений.
Утверждать, какие модели хуже действующих MICE-детекторов, нельзя: сопоставимого изолированного baseline в этом эксперименте нет, рабочая система не запускалась. Готовые detector outputs не использованы как признаки. Алгоритмические форматные детекторы не заменяются NER.
Следующий шаг: независимая человеческая NER-разметка, полный OCR, matched baseline MICE на отдельном согласованном стенде, затем отдельный calibration split (не B-350). Никакой интеграции или автоматической публикации.
