# Follow-up infrastructure fixes — 2026-11-27

- Targeted infrastructure/import suite: **69 passed** (isolated temporary venv).
- Ruff and Python syntax compilation for changed Python files: passed.
- JSON jobs accept `max_steps: -1`; tests verify dry-run, invalid values and
  unchanged forwarding of both max_steps and epochs to all mock training calls.
- PyTorch version checks allow identical public releases across official CPU/CUDA
  wheel suffixes (including `+cu132` versus `+cpu`), with tests for both neural
  engines and both directions. Public release/prerelease/dev mismatches, custom
  suffix mismatches and other critical dependency mismatches remain rejected.
- This verifies compatibility policy, not actual weight loading across installed
  PyTorch builds. No real model training, inference, GPU smoke checks, benchmark,
  model downloads or working-database access were performed in this follow-up.
  Existing trusted-import CPU inference validation remains unchanged.

# Infrastructure verification — 2026-11-27

- Isolated Python environment: `/tmp/mice-trainer-infra-venv`, Python 3.12.
- `python -m pytest tests/test_trainer_infrastructure.py tests/test_trainer_import.py -q`: **33 passed**.
- Ruff 0.17.6 on all changed Python modules: passed.
- `python -m py_compile` on all changed Python modules: passed.
- `trainer.py run-job --help`: passed; `git diff --check`: passed.
- Tests cover JSON validation, dry-run without writes/training, sequential mock
  orchestration for all five models with identical splits, optional mock external
  evaluation, failure reporting/input cleanup, single/multi-model packages,
  manifest/hash/report corruption, unsafe paths/symlinks/duplicates/size limits,
  categories/version checks, trust, selected import, inactive creation,
  legacy CLI folder import, access denial, web preview/import and real Django
  template parsing/rendering. CPU inference is mocked, not quality-evaluated.
- Legacy import tests now use inert fixtures instead of fitting TF-IDF.
- No model training, GPU checks, dataset generation, downloads of model weights,
  classification-quality evaluation or benchmarks were run.
- No working database was accessed. Server-facing checks use ORM/transaction
  doubles and a Django configuration with `DATABASES={}`. Full project database
  integration, actual MLModel persistence in PostgreSQL, browser end-to-end and
  production proxy upload limits were **not** tested: no isolated project DB/server
  deployment was provisioned. Existing model algorithms and active rows are untouched.
- Native stdout from compiled libraries may require external CLI log capture;
  per-model logs capture Python stdout/stderr. Exact library-version checks are
  deliberately conservative. Runtime validation of real artifacts is deferred
  to trusted model import, not performed during this infrastructure stage.

# Реальные проверки — 27 ноября 2026

## Среда

- WSL2/Linux; NVIDIA GeForce RTX 4060, около 8 ГБ VRAM.
- Python 3.14.4, окружение `/home/user/.venvs/mice-trainer`.
- PyTorch 2.15.0+cu132, CUDA runtime 13.2, драйвер 620.73.02.
- scikit-learn 1.9.1, Transformers 5.23.0, SetFit 1.2.0,
  sentence-transformers 6.3.0, datasets 5.2.0, accelerate 1.16.0.
- Установщик выполнен успешно; `pip check`: No broken requirements found.
- CUDA доступна; реальное умножение двух матриц единиц 512×512 на GPU
  вернуло 512.0. Диагностика: `/home/user/mice-trainer-data/logs/doctor.json`.
- База: cointegrated/rubert-tiny2,
  revision `e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae`.

## Обучение, экспорт, CPU reload

Запущен `/home/user/Mice/tools/mice-trainer/smoke_check.py`.
60 строк, 15 групп; 36/12/12 строк train/validation/test.
Штатные TF-IDF/LogisticRegression, SetFit и RuBERT, без альтернативных алгоритмов.
Нейросети: CUDA, batch size 8, seed 42, 3 optimizer steps для smoke.

| Движок | Категория | Validation F1 | Test F1 | Порог | CPU reload/evaluate |
|---|---|---:|---:|---:|---|
| TF-IDF | financial-plans | 1.000 | 1.000 | 0.7 | PASS |
| TF-IDF | pricing | 1.000 | 1.000 | 0.7 | PASS |
| SetFit | financial-plans | 1.000 | 1.000 | 0.6 | PASS |
| SetFit | pricing | 1.000 | 1.000 | 0.6 | PASS |
| RuBERT | financial-plans | 0.667 | 0.667 | 0.4 | PASS |
| RuBERT | pricing | 0.800 | 0.800 | 0.5 | PASS |

Все категории имеют префикс `pack-ru2-`. RuBERT financial-plans не прошёл
quality gate 0.7, что корректно отражено в `eligible=false`.
**Эти показатели не являются оценкой производственного качества:** fixture
намеренно простой, содержит повторяющиеся шаблоны между разными smoke-группами.
Тест проверяет исполнение и соблюдение заданных ID групп, но не качество
семантической группировки. Отдельный 8-строчный fixture проверяет evaluate,
а не заменяет независимый B-1000.

Артефакты и машинный отчёт:
`/home/user/mice-trainer-data/output/smoke-20261127T062422376444Z/results.json`.
Логи: `/home/user/mice-trainer-data/logs/smoke-20261127T062422376444Z/`.
Полный результат запуска: `/home/user/mice-trainer-data/logs/smoke-suite.log`.
Все пять моделей экспортированы в штатном формате, затем загружены в отдельных
процессах с `CUDA_VISIBLE_DEVICES=''` через `app.ml_runtime.infer_models`.
CPU-инференс выполнялся без установки/старта сервера.

Для TF-IDF и financial-plans каждого нейросетевого движка выполнено повторное
обучение с тем же seed. Совпали split.json, метрики и CPU confidence/решения
на контрольном тексте; совпали confusion-метрики отдельного fixture.
Байтовая идентичность ZIP не требуется (ZIP содержит timestamps).
Отсутствие пересечения назначенных group_id между частями проверено для всех
пяти моделей. Тесты отдельно проверяют конфликтующие группы и text overlap.

Дополнительно обнаружена и исправлена особенность SetFit/Transformers 5:
параметр устройства encoder сам по себе не заставляет внутренний Trainer
работать на CPU. Проверен реальный SetFit `--device cpu` при доступной RTX 4060,
1 шаг, успешное обучение/экспорт и проверка фактического устройства.
Лог: `/home/user/mice-trainer-data/logs/setfit-explicit-cpu-v2.log`.
После этого исправления повторно выполнен SetFit `--device cuda`, 1 шаг,
с успешным контролем фактического CUDA-устройства и экспортом:
`/home/user/mice-trainer-data/logs/setfit-final-cuda.log`.

## Автоматические проверки

Команда из README: 24 passed (ML, dataset, standalone и import command tests).
Проверены произвольные/multilabel категории, дубликаты, конфликтующая разметка,
seed, group leakage, TF-IDF воспроизводимость, повреждённый экспорт,
отклонение пересекающегося evaluation, dry-run без записи и inactive commit.
Серверная команда проверяется с ORM/Django doubles, без установки Django и БД;
при этом TF-IDF-инференс в тесте команды реальный, не mock.
`ruff check`, `compileall`, `bash -n`, `git diff --check` проходят.

Полный серверный test suite в изолированном Trainer-окружении не собирается:
6 collection errors из-за отсутствующих серверных зависимостей (например,
python-docx, razdel). Они намеренно не устанавливались. Лог:
`/home/user/mice-trainer-data/logs/collect-tests.log`.
Исправлен существовавший устаревший тест `infer_active`, теперь проверяющий
действительный публичный API `infer_models`.

## Ограничения и оставшиеся проверки

- B-6000/B-1000 не обучались/не оценивались; их качественная семантическая
  группировка и полнота разметки остаются ответственностью автора корпуса.
- PostgreSQL/Django-сервер не установлен и не запущен, рабочая БД не изменялась.
  Реальный ORM import на существующем сервере ещё должен выполнить администратор;
  проверка сериализации/CPU runtime выполнена локально для всех движков.
- TF-IDF сохраняет штатное требование минимум двух категорий; нейросети обучаются
  по одной категории за запуск. Число пользовательских категорий не фиксировано.
- Повторяемость проверена на этой среде; не заявляется побитовая идентичность
  между разными GPU, версиями CUDA/библиотек или платформами.
- Веса/журналы/обучающие данные не добавлены в Git. Модели не публиковались,
  PR не объединялся. PR #29 остаётся stacked на PR #28.