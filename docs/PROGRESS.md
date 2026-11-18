# Фактическое состояние

Обновлено: 18 ноября 2026.

## Реализовано и проверено
- Python 3.12 / uv.lock, FastAPI, SQLAlchemy, начальная Alembic миграция.
- Миграция и bootstrap действительно выполнены на PostgreSQL 17 / pgvector
  в контейнере `mailfire-test-db`, порт localhost:55432.
- PostgreSQL хранит оригиналы, бинарные объекты, письма, события, задания,
  адреса, извлечённый текст, политики, инциденты, аудит и серверные сессии.
- EML parser и отдельная ветка extract-msg; подлинный MSG пока не протестирован.
- Приём оригиналов с ограничением размера, идемпотентным source key,
  SHA-дедупликацией бинарных объектов, независимыми почтовыми событиями.
- Файловый сканер со стабильностью файла и базовым отказом от symlinks.
- Базовая очередь SKIP LOCKED / lease / retry; heartbeat ещё отсутствует.
- Извлечение TXT/HTML/PDF/DOCX/XLSX/PPTX/ZIP; ошибки не считаются безопасностью.
- Статические правила ПДн/email/телефон/ИНН, секретов, кода и injection.
- Базовые политики и инциденты, решения и комментарии, переанализ.
- Argon2, cookie sessions, CSRF, роли, отдельное разрешение оригиналов.
- React/TypeScript интерфейс с реальными API: импорт, письма, инциденты,
  очередь, базовый мониторинг, аудит, списки политик и адресов.
- 13 тестов проходят на настоящей БД, включая API авторизацию/CSRF/импорт.
- Frontend build проходит; Ruff проходит. Предупреждение Starlette TestClient.

## Не готово / необходимо продолжить
- Полный запуск Compose, healthchecks workers, отказоустойчивость и нагрузка.
- Изоляция недоверенных парсеров без секретов/доступа к БД и сети.
- Реальные OCR Paddle/Rapid, Presidio, Gitleaks, ClamAV/YARA/oletools.
- MSG fixture/integration, безопасный ZIP upload, пакетные задания импорта.
- Нормализованные получатели, история identity/aliases, trusted direction.
- Heartbeat, fencing результатов, timeout и отдельные тяжёлые очереди.
- Полный Policy Engine, версии/история/shadow evaluations и исключения.
- SIEM/уведомления, retention/legal hold cleanup, FTS API.
- Эталоны/MinHash/embeddings, настоящее контролируемое ML/rollback.
- Исторические метрики, диагностика контейнеров, уведомления самодиагностики.
- Расширение UI, RBAC-аудит, маскирование, login rate limit, E2E/security/load.
- `npm audit`: 4 high в build dependency chain picomatch/fdir/tinyglobby/vite;
  обновление latest автоматически проблему не устранило. Не скрывать её.

Проект — незавершённая разработка, не готов к промышленному использованию.

## Продолжение сессии: проверенные изменения
- Создан локальный Git checkpoint b0b8160; удалённая публикация не выполнялась.
- Создан игнорируемый `.env` со случайными локальными паролями.
- Compose config, сборка всех образов и `docker compose up -d` успешно выполнены.
  PostgreSQL и API healthy; web/importer/worker/SMTP запущены. У последних
  пока нет самостоятельных healthchecks.
- Через nginx: UI 200, /api/health OK, login 200, ML статус UNTRAINED.
- Реальный файловый импорт трёх синтетических EML: 3 ANALYZED, 6 DONE jobs,
  3 инцидента в Compose PostgreSQL; исходные файлы сохранены.
- Heartbeat очереди, fencing завершения по owner/lease, recovery-тест.
  Полное fencing записи результатов ещё не реализовано.
- Безопасный ограниченный ZIP upload endpoint, security-тесты ZIP.
- Исключение .imported из сканирования, обработка исчезновения файла.
- Настоящий ML baseline TF-IDF + logistic multilabel, дедупликация групп,
  train/validation/test, validation thresholds, per-label precision/recall/F1,
  quality gate, хранение артефактов в БД, publication/rollback API.
  Подключён к анализу почты. RuBERT/SetFit и ML UI ещё отсутствуют.
- Финальный запуск: **25 passed**, 1 deprecation warning, настоящая тестовая БД.
  Ruff и compileall проходят. См. KNOWN_LIMITATIONS.md.

## Следующий реализованный блок
- Парсинг mail/attachments вынесен в subprocess с очищенным environment,
  seccomp deny network/ptrace/mount и rlimits CPU/RAM/files. Тесты подтверждают
  отказ socket и отсутствие DATABASE_URL. Это не полная filesystem isolation.
- Установлены RapidOCR/ONNXRuntime/Pillow с uv.lock. Реальный английский OCR
  изображения проходит напрямую и в sandbox; сохраняются box/confidence/page.
  PDF без текста и изображения подключены к OCR при включённом backend.
  Paddle adapter добавлен, но Paddle не установлен/не проверен; русский OCR
  и многостраничные изображения ещё требуют реализации/проверки.
- SIEM transactional outbox, HTTP JSON с idempotency header, UDP JSON/CEF,
  bounded timeout/backoff/dead state; admin integration API. Реальные HTTP и
  UDP endpoint тесты проходят. UDP не обеспечивает подтверждённую доставку.
- Maintenance service добавлен для outbox и CPU/RAM/swap/disk метрик в БД.
- PostgreSQL FTS API, attachment listing/download с отдельным разрешением/аудитом.
- Эталоны: загрузка/извлечение, SHA/MinHash/shingles и объяснимое совпадение
  фрагментов, подключение к DLP. Embeddings/pgvector semantic search ещё нет.
- Retention config API, dry run, explicit deletion confirmation, legal hold,
  reference-aware удаление писем/общих blobs и производных данных. Тест на БД
  подтверждает legal hold и фактическое удаление. Автозапуск cleanup не включён.
- **34 passed**, 1 warning на настоящей PostgreSQL; Ruff проходит.
- Эти изменения пока НЕ пересобраны в работающих Compose контейнерах:
  работающий стенд остаётся на предыдущем image. Следующий шаг — UI интеграция,
  контейнерная пересборка/проверка OCR и закрытие ограничений безопасности.

## Контейнерная проверка и развитие
- Последние образы пересобраны и запущены; успешный повторный live сценарий
  описан в CONTAINER_VALIDATION.md. Регрессия отсутствующих OCR weights исправлена.
- Русский RapidOCR в контейнере действительно распознал кириллицу (0.98989).
- Outbox SENT и фактическое retention deletion подтверждены внутри контейнеров.
- Автоматический retention добавлен в maintenance с часовым интервалом;
  paused учитывается. Политика использует существующие значения по умолчанию.
- Мониторинг API расширен: поток почты по часам/источникам/направлениям,
  распределение размеров, очереди/expired leases/p95 полного времени,
  PostgreSQL размеры/индексы/autovacuum/connections/locks, история ресурсов.
- UI: эталоны, ML-разметка/обучение/публикация/откат, retention, SIEM destinations
  и outbox, диагностические запросы; ZIP chooser. Build прошёл.
- 35 tests passed / 1 warning. Семантические embeddings всё ещё не реализованы.