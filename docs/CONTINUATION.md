# Продолжение UI/UX после 2026-11-18

Сначала читать UI_UX_DESIGN.md: содержит реализованное и открытые пункты.
Последний полный pytest: 39 passed, /tmp/mailfire-ui-final-tests.log.
Browser: /tmp/mailfire-ui-browser2.log, scripts/ui_smoke.cjs.
Compose api/web пересобраны; 0003 применена без удаления данных.
Продолжить полноценные analytics/address statistics, reference management,
ML tabs/incident labeling, system telemetry, settings/access CRUD и E2E.
Не считать smoke проверкой 1000+ записей/60k daily или всех разрешений.
Фронтенд пока содержит длинные JSX-строки; требуется декомпозиция/форматирование.
Не менять шлюз, не удалять PostgreSQL volume, не выполнять push.

# Продолжение

Сначала прочитать PROGRESS.md, IMPLEMENTATION_PLAN.md, git status и реальные
исходники. Не принимать наличие ORM-таблицы за готовую подсистему.

Рабочая директория: /home/user/Mail-Fire. Python управляется uv, .python-version=3.12.
Для frontend доступен Node 22 в /tmp/mailfire-node/node-v22.21.1-linux-x64/bin;
системный Node 12 слишком стар и npm отсутствует.

Тестовая PostgreSQL: контейнер mailfire-test-db, localhost:55432, database/user
mailfire. Пароль исключительно синтетической одноразовой БД задан при создании
контейнера; извлекать из docker inspect, не публиковать в документации.
Не удалять volume/БД пользователя. У тестового контейнера нет production данных.

Команды:
```
uv sync --frozen
uv run ruff check app tests scripts migrations
uv run pytest -q
# Для полной проверки задать DATABASE_URL тестовой БД и MAILFIRE_TEST_DB=1.
# API test ожидает пароль синтетического bootstrap; см. tests/test_api.py.
uv run alembic upgrade head
uv run python -m app.bootstrap
cd frontend && npm ci && npm run build
```

Последние результаты: 13 passed, 1 TestClient deprecation warning; UI build OK.
Compose config не прошёл из-за отсутствующего .env; требуется создать .env
с рандомными локальными секретами, не включать его в Git.

Следующие приоритеты: checkpoint Git и документация; Compose live verification;
исправить importer archive reimport и symlink ancestor race; очередь heartbeat
и fencing; безопасный ZIP upload; затем sandbox extraction/OCR и другие этапы.

## Актуализация после продолжения
Compose уже собран и запущен. UI localhost:8080, API localhost:8000.
Локальный .env создан со случайными секретами (не коммитить). В compose БД
проверен импорт 3 синтетических писем: 3 ANALYZED / 6 DONE / 3 incidents.
Тестовая отдельная БД mailfire-test-db остаётся на :55432.
Последние тесты: 25 passed, 1 warning. Добавлены heartbeat и lease completion
fencing, ZIP upload, настоящий ML baseline с API в app/ml_api.py.
Точка входа теперь app.main:app (включает ML router).
Не путать ML baseline с выполнением RuBERT/SetFit требований.
Приоритет: sandbox parser без DB credentials/network, реальный OCR;
полное fencing derived results; UI ZIP/ML; нормализация событий/получателей;
SIEM/retention/эталоны/диагностика. Далее остальные пункты плана.

## Последний блок
34 tests passed / 1 warning; uv.lock обновлён (rapidocr, onnxruntime, pillow).
Добавлены sandbox.py, ocr.py, integrations.py, maintenance.py, admin_api.py,
fingerprints.py/reference_api.py, retention.py/retention_api.py.
OCR по умолчанию disabled; для проверки RAPIDOCR задать OCR_BACKEND=rapidocr.
Модели RapidOCR входят в установленный пакет; загрузка через сеть sandbox
запрещена. Реальный english image OCR проверен внутри sandbox.
Paddle adapter непроверен. Полного filesystem sandbox нет; нельзя объявлять
секреты недоступными через /proc/fs только из-за очистки environment.
Compose всё ещё использует предыдущие образы: пересобрать и проверить.
UI новых подсистем ещё отсутствует. Retention не запускается автоматически.
Embeddings и полноценный semantic search не реализованы.

## Последнее продолжение
Читайте CONTAINER_VALIDATION.md: последние образы уже пересобраны/запущены.
Русский OCR исправлен явной моделью Rec.model_path; prepare_ocr.py материализует
кириллическую модель в installed rapidocr/models при Docker build.
35 passed / 1 warning; frontend build OK. UI Operations.tsx добавлен.
Maintenance теперь запускает retention автоматически каждый час, до 100 писем.
monitoring.py добавляет read-only PostgreSQL/queue/flow/resource endpoints.
Приоритеты: настоящий filesystem/container sandbox, semantic embeddings/pgvector,
полноценные healthchecks/diagnostic agent, RBAC UI actions, browser E2E,
Paddle primary, ML advanced и остальные исходные требования.

## Последнее состояние изоляции
Parser теперь отдельный Compose service (app.parser_service), без env_file и
mounts, internal parsing network, ограничения ресурсов, non-root/read-only.
app.sandbox.call использует PARSER_URL в API/worker; local_call оставлен для
тестов и broker. Недоверенный child seccomp запрещает sockets.
Реальные проверки: scripts/check_isolation.py и scripts/container_checks.py
прошли после build/up. Не возвращать парсинг в DB-connected worker.
Далее: semantic embeddings/pgvector, Paddle primary и остальные требования.
Важно: broker использует тот же image с лишними установленными зависимостями;
минимизация image желательна. Internal network не заменяет seccomp child.

## Последний semantic checkpoint
Добавлена миграция 0002 и app/semantic.py, semantic_api.py. FastEmbed использует
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, 384 dims; weights
build-time /opt/embedding-models. Локальные тесты: EMBEDDING_CACHE_DIR=
/tmp/mailfire-embedding-models MAILFIRE_EMBEDDING_TEST=1. Suite 37 passed.
Compose пересобран/запущен, cross-language query проверен (.882 vs .030).
API /api/semantic/search, /status, /reindex (до 1000 docs/type синхронно).
Продолжить Paddle primary, RuBERT/SetFit/analyst decisions, semantic UI,
container diagnostics и browser E2E. Не повторять изоляцию без критичной причины.
В semantic_chunks есть 2 синтетических тестовых источника semantic-synthetic-*
без Reference rows; это явно тестовые данные cross-language проверки.
Последний визуальный этап: Reference-UI перенесён частично в React — navy
sidebar с SVG, breadcrumbs, cards/tables/badges, dashboard grid. Исходный
Reference-UI пользовательский: не изменять и не включать в commit автоматически.
Smoke /tmp/mailfire-reference-smoke.log прошёл, web Compose обновлён.
Пользователь просит экономить токены и запускать минимум необходимых тестов.

Последнее: theme icon light/dark (system в UI удалён), диаграмма категорий
по Policy.name, IncidentTable общий. Smoke: /tmp/mailfire-category-smoke3.log.
Ожидание PUT в smoke обязательно (400ms было недостаточно для persistence).

Toolbar refinement: health dot проверяет только /api/health (API+DB),
не все контейнеры; click -> system. Bell -> open incidents. Polling 10с
для лёгких списков/overview, без карточек и тяжёлых операций. Ещё требуется
дальнейшая унификация фильтров административных разделов и расширение health.

Management block: app/catalog_api.py + frontend/src/Management.tsx. Detector
switches применяются в processing.evaluate к новым findings, не отключают
сам inference/extraction. Реестр пока импортируется из catalog_api (следует
вынести в независимый модуль). Reevaluate bounded 1000 events, existing worker
kind evaluate; не пересчитывает сохранённые incident decisions. Reference
удаление сохраняет blob до retention и исторические findings. ML настоящий
TF-IDF baseline, НЕ RuBERT/SetFit. Проверь расширенные сценарии CRUD/permissions;
API smoke на disposable DB успешен, browser partial interruption отмечен.

Latest detail UX: Evidence.tsx (Summary/Evidence), main.tsx integration.
Build/smoke /tmp/mailfire-detail-{build,smoke}.log. Последний dist скопирован
в web, immutable image следует пересобрать при следующем deploy.

2026-11-18 functional hardening work in progress (not production acceptance):
- Added actual Presidio PatternRecognizers (RU INN/SNILS checksums, contextual passport, phone), YARA and oletools isolated scan operation, Gitleaks 8.30.1 checksum-pinned build installer and CLI adapter. New synthetic tests pass with local binary.
- Added Clamd INSTREAM adapter (disabled unless CLAMAV_HOST is set), optional Compose antivirus profile. Real ClamAV signatures/EICAR NOT yet verified.
- Training now enqueues ml_train and returns 202; worker lease-fenced model persistence, single live training claim, admin cancellation suppresses persistence but does not terminate native computation. Frontend accepts queued response. Progress currently only 0/100, no intermediate progress. Other heavy operations unchanged.
- Content digest includes binary attachment hashes and detector revision to avoid sharing binary evidence across different files with identical text.
- Ruff passes; 18 targeted tests pass; frontend build passes. PostgreSQL training/cancellation tests and browser regression NOT yet run.
- uv add paddleocr paddlepaddle still downloading at last check (/tmp/mailfire-paddle-install.log); dependencies/lock updated, runtime NOT verified. OCR default remains unchanged, no pretrained RuBERT/SetFit integration yet.
- First Docker build succeeded but snapshot predates final edits. Second build running (/tmp/mailfire-final-engines-build.log), no new deployment yet. Do NOT assume running services include these changes.
- User requests autonomous completion of full hardening scope; monitoring, RBAC audit, corpus metrics, admin CRUD and operational acceptance remain open. Preserve Reference-UI and PostgreSQL data.

Follow-up deployed: all standard Compose images successfully built and services recreated.
api/db/parser healthy, worker/importer/maintenance/smtp/web running. Browser smoke passes.
PaddleOCR 2.10 CPU RU+EN verified locally and inside deployed parser. 3.x conflicts
with current Presidio PyYAML constraints; exact 2.10 pinned. Compose default Paddle,
but existing OCR_BACKEND env override still takes precedence. RapidOCR retained.
Fixed native OpenCV runtime libs in Docker and Gitleaks WASM virtual allocation:
scan subprocess AS limit 8GiB, parser cgroup RSS remains 3GiB; other operations 3GiB.
Deployed sandbox Gitleaks/YARA reports OK and synthetic secret detected.
Added accounts API+settings UI, role/enable/original permissions/password updates,
session revocation, last-admin protection. Reindex durable per-document checkpoints,
admin jobs/alerts endpoints. 23 targeted tests passed including real Paddle/Rapid OCR.
Remaining NOT complete: RuBERT/SetFit, analyst-decision training flow, full corpus
and calibrated metrics, ClamAV real EICAR acceptance, per-container telemetry,
full security/failure-recovery audit, DB integration tests for new job handlers,
all administrative browser CRUD scenarios. Do not claim production readiness.
Logs /tmp/mailfire-{all-build,rebuild-fix,redeploy-fix,deployed-browser,hardening-final-tests}.log.
