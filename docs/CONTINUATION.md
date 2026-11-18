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