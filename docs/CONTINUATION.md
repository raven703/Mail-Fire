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