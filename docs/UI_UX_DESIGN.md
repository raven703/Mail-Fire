# Рабочее место аналитика — состояние на 18 ноября 2026

## Навигация
Три группы: мониторинг и расследования (обзор, инциденты, письма, аналитика),
анализ и политики (политики, эталоны, ML, адреса), администрирование
(импорт, очереди, состояние системы, журналы/аудит, настройки).
Настройки объединяют существующие SIEM/webhook и retention.

## Компоненты и визуальный язык
CSS tokens для светлой/тёмной тем; системная тема реагирует на настройки ОС.
Выбор сохраняется отдельно для аккаунта в PostgreSQL settings.
DateTimeRangeFilter: последние 24 часа / 7 дней / 30 дней / локальный
datetime-local диапазон, передаваемый серверу в UTC с offset.
Table, Badge, Timeline, Value, PolicyEditor, Queues: общие компоненты.
HIGH: risk >=70, MEDIUM: 40–69, LOW: <40. Текстовые бейджи дополняют цвет.
Основные таблицы без SHA, UUID и JSON; технические данные вынесены отдельно.
Email обрезается с title, без переноса по буквам. Строки доступны по Enter.

## Реализованные сценарии
Обзор → KPI/критичность → серверный список с сохранённым периодом.
Поиск писем → карточка → DLP → инцидент → связанное письмо.
Назначение аналитика, решение, комментарий; просмотр истории и связанных
инцидентов. Plain-text просмотр не исполняет HTML/скрипты/удалённые ресурсы.
Вложения доступны только с originals permission.
Фильтры/сортировка/страницы сохраняются в URL; поиск имеет debounce,
устаревшие fetch отменяются через AbortController.
Очереди показывают реальные задания/времена, не вымышленные стадии OCR/ML.
Создание/изменение политики: серверная проверка, версия, audit before/after.

## API и PostgreSQL
/api/workspace/messages: поиск темы/sender/recipients/headers/ID,
с разрешением originals — FTS/partial body и название вложения.
Комбинируемые фильтры периода, направления, источника, состояния,
инцидентов, критичности, вложений/MIME. Ограничение 200 строк, default 50.
/incidents: фильтры, сортировка, страницы; /overview: KPI, timeline, recent.
/messages/{id}, /incidents/{id}: детальные расследования.
/analysts, /incidents/{id}/assignee, /preferences, /policies и history.
Существующие API сохранены. 0003 добавляет pg_trgm GIN и join/filter indexes;
бинарные EML при открытии обзора не читаются.

## Фактические проверки
Frontend TypeScript/Vite build, Ruff, git diff --check прошли.
Полный pytest с реальной моделью и disposable PostgreSQL: 39 passed,
1 TestClient deprecation warning (финальный запуск 47.80 s).
Compose api/web пересобраны/запущены, migration 0003 применена.
container_checks: импорт, Russian OCR/reference, FTS, legal hold прошли.
Chromium smoke: вход, три темы, восемь разделов, partial email search,
карточка письма, отсутствие JS pageerror. Это НЕ полный E2E всех требований.
Скрипт /home/user/Mail-Fire/scripts/ui_smoke.cjs требует Playwright;
в текущей среде PLAYWRIGHT_MODULE=/tmp/mailfire-browser/node_modules/playwright,
LD_LIBRARY_PATH=/tmp/mailfire-browser/root/usr/lib/x86_64-linux-gnu.
Скриншоты: /tmp/mailfire-dashboard.png, /tmp/mailfire-message.png.

## Ещё не реализовано / не проверено
Полная аналитика доменов/адресов/ресурсов, PDF/экспорт расследования,
policy exceptions/test-on-mail UI, полнофункциональные employees/aliases,
reference delete/reindex/matches UI, шесть полноценных ML-вкладок,
ML-разметка непосредственно из инцидента, CRUD аккаунтов и все settings tabs.
Нет достоверной per-container telemetry; UNKNOWN не маскируется под OK.
Диагностика пока использует универсальные структурированные поля, не все
названия локализованы. Нет безопасного HTML preview (показан только текст).
Нет подтверждения нагрузки 60k/day или браузерной проверки 1000+ записей.
ZIP происхождение отдельно не сохранено старой моделью ingestion, поэтому
фильтр ZIP не предлагается. Направление зависит от сохранённых mail events.
Существующая дедупликация инцидентов event/policy не изменена: между разными
событиями одного письма всё ещё возможны отдельные инциденты.
Требуются дополнительные permission E2E, pagination/ranking/period edge tests,
проверка переходов во всех сочетаниях фильтров и query-plan/load profiling.
Работа является промежуточным блоком, не завершением полного ТЗ.
## Перенос Reference-UI
Тёмная navy-навигация с SVG-иконками из локального референса, breadcrumbs,
компактные карточки, двухколоночная сводка, округлые статусы и улучшенная
типографика. Основной текст таблиц 13px вместо 9–10px в прототипе.
Реальные API сохранены; demo JS/цифры не используются. Внешние Google Fonts
не подключены. Проверки: frontend build и один Chromium smoke на Compose
(разделы, темы, partial search, карточка письма, без JS pageerror).
Это визуальный этап; перечисленные выше функциональные ограничения остаются.
