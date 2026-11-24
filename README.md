# MICE

Пассивный анализ копий почты: Django + HTMX, Celery, RabbitMQ,
PostgreSQL/pgvector, Nginx, изолированные Parser, OCR и LibreOffice Converter.
React, FastAPI, SQLAlchemy и Alembic не используются.

## Локальный запуск

```sh
cp .env.example .env
# Заменить секреты; ADMIN_PASSWORD — минимум 16 случайных символов.
docker compose up -d --build
docker compose exec -T web python manage.py initialize_mice
```

Интерфейс: http://localhost:8080. Пользователь admin, пароль из .env.
Инициализация не меняет существующий пароль. Системные категории создаются миграциями.
HTTP и MICE_COOKIE_SECURE=false допустимы только локально. Для удалённого
доступа необходимы TLS и MICE_COOKIE_SECURE=true.

Основной pipeline запускается по умолчанию. ML/LLM inference выключены.
SMTP, импорт каталога, обучение и semantic включаются только явными profiles.
Модели data/models и тестовые наборы необходимо сохранять отдельно от БД.
Не применять глобальный Docker prune.

## Проверки

```sh
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py test identity records pipeline policy_engine --noinput
docker compose ps
```

EML/MSG загружаются на странице «Импорт почты». Прикладные данные хранятся
в PostgreSQL. Не подключать реальные враждебные файлы без отдельной
оценки безопасности и нагрузочного тестирования.
