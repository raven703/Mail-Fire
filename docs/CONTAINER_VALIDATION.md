# Проверки контейнерного стенда — 18 ноября 2026

Все последние образы пересобраны, Compose запущен, включая maintenance.
API/PostgreSQL healthy. Тесты выполнялись на синтетических данных.

## Подтверждено
- nginx/UI/API login доступны.
- `PYTHONPATH=. uv run python scripts/container_checks.py` проходит:
  загрузка эталона, EML с изображением, OCR, reference finding, FTS,
  sandbox network denial и legal hold/dry-run retention.
- Последний успешный run: 7ff636fec8e04059b8cd16eb6dad3eea;
  message 3b84817a-be6d-4f15-8c12-1d2e0d5a16d1, ANALYZED.
- Outbox в maintenance доставил синтетический JSON настоящему HTTP endpoint
  внутри контейнера; запись в PostgreSQL имеет SENT (1 запись).
- Созданное просроченное синтетическое письмо удалено cleanup в worker:
  retention_deleted=1, synthetic_message_removed=true.
- Русское изображение передано через stdin в worker, затем sandbox:
  «КОНФИДЕНЦИАЛЬНЫЙ ФИНАНСОВЫЙ ОТЧЕТ», ANALYZED, confidence 0.98989.
- Добавлен regression test русского OCR; полный suite: 35 passed / 1 warning.
- UI TypeScript/Vite build проходит. Новые страницы имеют реальные API calls;
  полноценные browser E2E пока не выполнены.

## Найденные и исправленные дефекты
1. Default RapidOCR модель не распознавала кириллицу. Выбрана Cyrillic
   PP-OCRv5 mobile; английские OCR regression tests продолжают проходить.
2. После смены модели sandbox пытался скачать отсутствующие веса и возвращал
   PARTIAL/DownloadFileException. Веса теперь явно включаются в image на build,
   runtime использует явный model_path. Повторная контейнерная проверка прошла.
3. Генератор изображения через PyMuPDF builtin notos не работал в образе;
   проверка заменена передачей синтетического PNG через stdin, без установки
   тестовых файлов или пользовательских данных в постоянное хранилище.

## Не является подтверждением полной безопасности
Seccomp блокирует сеть, но не закрывает файловый доступ к /proc и секретам
родительского контейнера. Изолированного parser-container без секретов ещё нет.
Retention deletion проверено явно; ожидание часового scheduler не выполнялось.
SIEM HTTP endpoint был локальным контейнерным тестом, не внешним production SIEM.