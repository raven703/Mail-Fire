# Изолированный HF GPU benchmark

Никакого импорта `app`, Django или MICE runtime. Только frozen-weight inference
в отдельном venv. Рабочий код/контейнеры/БД/категории/политики не меняются.

## Уже выполненный прогон

См. `results/REPORT.md`, `summary.csv`, `errors.csv`, `predictions.jsonl`,
`performance.json`, `environment.json`. `model_audit.json` содержит точные
ревизии, архитектуры, штатные labels, лицензии и причины ограничений.
Не сравнивать F1 разных задач и не трактовать B-350 как production validation.

## Окружение и повтор

Проверено на WSL2, Python 3.14, RTX 4060. Установка не использует sudo/apt/Docker.
Пример абсолютного checkout path — `/home/user/Mice`:

```bash
bash /home/user/Mice/test-data/hf-model-benchmark/install.sh
/home/user/.venvs/hf-model-benchmark/bin/python -m pytest \
  /home/user/Mice/test-data/hf-model-benchmark/test_benchmark.py -q
```

`requirements.lock` — полный pip freeze отдельного окружения. Пакеты не берутся
из Trainer venv. `HF_BENCHMARK_ENV` меняет venv; `PYTHON` выбирает интерпретатор.
Веса и download/log/cache хранятся в `/home/user/hf-model-benchmark-data/`, не в Git.
Нужен доступ к Hugging Face, CUDA и несколько ГБ RAM/диска для моделей.

Для нового прогона используйте **отдельную копию benchmark-каталога с пустым
results/** внутри другого checkout, не перезаписывая опубликованные результаты:

1. `audit.py` проверяет доступность всех шести точных repo, разрешает SHA ревизий
   и фиксирует конфиги. Не исполняет скачанный Python. Для точного повтора
   сохраните опубликованный `model_audit.json`, не разрешайте `main` заново.
2. `prepare.py` читает оригинальные EML, извлекает MIME и вложения, сохраняет
   segments/offsets/source/hash и extraction errors. Не читает manifest hints
   `attachment_visible_text` и готовые detector outputs.
3. До GPU inference сохраните/закоммитьте `protocol.json`, `ner_fixture.json`,
   `cohorts.json`, `prepared.jsonl`, `model_audit.json`. Все 350 ID фиксируются,
   исключения по качеству ответов запрещены.
4. `run.py` проверяет SHA-256 исходников/протокола и доступность CUDA,
   запускает модели **последовательно** отдельными процессами. Для каждой:
   загрузка → 5 smoke probes → основной прогон → release CUDA memory.
   Ошибки одной модели фиксируются, остальные продолжают работу.
5. `summarize.py` рассчитывает метрики из сохранённых предсказаний, не меняет
   пороги, веса или эталоны. Перегенерирует итоговые CSV/JSON/REPORT.

```bash
/home/user/.venvs/hf-model-benchmark/bin/python /home/user/Mice/test-data/hf-model-benchmark/run.py
/home/user/.venvs/hf-model-benchmark/bin/python /home/user/Mice/test-data/hf-model-benchmark/summarize.py
```

`run.py` отказывается перезаписывать существующий environment.json,
worker — predictions.jsonl. Для технического retry до появления предсказаний
можно запустить `run.py --worker MODEL_KEY`, сохранив историю ошибки отдельно.
Не используйте retry для изменения гипотез/порогов по результатам B-350.

## Задачи и честные ограничения

- Horizon/mDeBERTa: одинаковые 7 описаний и independent multi-label scoring.
  Порог 0.5, FP32, без калибровки на B-350. Все raw NLI logits сохраняются.
- Redmadrobot: качественный NER-прогон всех писем; B-350 не содержит spans.
  Нет ложных document-category F1 для NER. Отдельный AI-authored synthetic
  fixture с явно написанными spans — лишь проверка механики; он не является
  независимой ручной человеческой разметкой. Полноценный NER benchmark не заявлен.
- ScienceSoft: int8 ONNX CPU-only release; CUDA/Transformers прогон заблокирован,
  без скрытого CPU fallback, конвертации, модификации весов или другой модели.
- Gloomreach: штатные 3 sigmoid головы из опубликованного `model.py` реализованы
  локально и проверены strict load полного state_dict. Не используем неправильный
  AutoModelForSequenceClassification со случайными головами. Only threat scored.
- Aleksandr505: Phishing=0/Legit=1, softmax; лицензия не указана.
- Если OCR executable отсутствует, PNG отмечены extraction-limited, а не
  заменены текстом из эталона. Для полного OCR нужен отдельно согласованный
  extractor; такой прогон должен иметь новую extraction revision.
- Высокий score NER не означает нарушение политики. Организации и имена могут
  законно упоминаться в безопасной переписке. ИНН/паспорт/СНИЛС — прежде всего
  алгоритмические детекторы; не оцениваем отсутствие неподдерживаемых labels.

Никаких рекомендаций production без независимых данных, экспертной проверки,
matched baseline и правового согласования. Модели/веса не публикуются с кодом.