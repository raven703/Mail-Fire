# OCR benchmark-350 — фактически выполненные проверки

## Методика

Исходные 350 EML прочитаны без импорта в БД; SHA-256 каждого EML проверен после прогона. Распознаны 10 растровых/PDF вложений. Из прежнего опыта Surya использованы 6 эталонов, совпадающих по SHA-256. CER/WER ниже — macro-average на этих 6 образцах; не оценка всего русского корпуса.

Один документ за раз, CPU, существующий sandbox и неизменённые детекторы. Wall time включает запуск sandbox, HTTP/Docker и запуск проверки детекторов; OCR time — сумма измерений адаптера. Холодная инициализация входит в OCR time.

| Провайдер | Вложений | CER (6) | WER (6) | Точный идентификатор (3) | OCR, с | Wall, с |
|---|---:|---:|---:|---:|---:|---:|
| rapidocr | 10 | 0.0650 | 0.1333 | 3/3 | 169.60 | 321.83 |
| paddleocr | 10 | 0.4661 | 0.7333 | 0/3 | 131.46 | 260.51 |
| Surya 0.14.7 | не завершено | — | — | — | — | — |

## Ограничения

- Предыдущие материалы Surya 2.5 содержат скрипт, inputs.json и 6 PNG, но не results.json/environment.json. Поэтому результаты прошлого запуска не выдумываются и не переносятся на 0.14.7.
- Эталонные 6 изображений содержат преимущественно латиницу/цифры. Полноценную точность русского текста, СНИЛС и русского паспорта этот поднабор не доказывает. Нужен размеченный русский корпус.
- GPU в среде не проверен, VRAM не измерена. CPU-прогоны не используют GPU.
- Выборка docker stats начата только в конце прогона: не выдаётся за полный peak RAM. Сырые выборки: /home/user/mice-archives/ocr-resources.log.
- Срабатывания неизменённых детекторов сохранены для каждого документа в JSON. Производственные правила/политики не изменялись.

## Ошибки и тексты (синтетические benchmark-данные)

### rapidocr

- **MF350-0304** — ANALYZED; CER=0.13333333333333333; detector findings=0
  - OCR: 'PUBLIC\nTEST\nSYNTHETIE\nOCR\nTEST'
- **MF350-0308** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PUBLIC OFFER\nSYNTHETIC PDF FIXTURE'
- **MF350-0311** — ANALYZED; CER=0.15151515151515152; detector findings=2
  - OCR: 'INN\n7707083893.\nSYNTHETIC\nOR\nTEST'
- **MF350-0316** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PASSPORT 4510123456\nSYNTHETIC PDF FIXTURE'
- **MF350-0319** — ANALYZED; CER=0.0; detector findings=2
  - OCR: 'INN 7707083893\nSYNTHETIC OCR FIXTURE'
- **MF350-0324** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PRIVATE BUDGET 2450000\nSYNTHETIC PDF FIXTURE'
- **MF350-0327** — ANALYZED; CER=0.0; detector findings=0
  - OCR: 'PRIVATE BUDGET\nSYNTHETIC OCR FIXTURE'
- **MF350-0335** — ANALYZED; CER=0.0; detector findings=0
  - OCR: 'SABOTAGE TEST\nSYNTHETIC OCR FIXTURE'
- **MF350-0340** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'CREDENTIAL TEST\nSYNTHETIC PDF FIXTURE'
- **MF350-0348** — ANALYZED; CER=0.10526315789473684; detector findings=0
  - OCR: 'PASSPORT\n4510123456\nSYNTHETIC\nOR\nTEST'

### paddleocr

- **MF350-0304** — ANALYZED; CER=0.6; detector findings=0
  - OCR: "LEL\nTET\nIT'HTHETII\nF.\nTETT"
- **MF350-0308** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PUBLIС\nOEEER\nSNTHETIС\nРDЕ\nFIХTURE'
- **MF350-0311** — ANALYZED; CER=0.8181818181818182; detector findings=0
  - OCR: 'гчгч\nITEFEHIEIIEE\nITHTHETII\nF.\nTE-T'
- **MF350-0316** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PASSPORT\nозза5\nSNTHETIС\nРDЕ\nFIXTURE'
- **MF350-0319** — ANALYZED; CER=0.2777777777777778; detector findings=0
  - OCR: 'INN\nоо8383\nSYNTHETIC\nOСR\nFIXTURE'
- **MF350-0324** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'PRIVАTE\nBUDGET\nз45оооо\nSNTHETIС\nРDЕ\nFIXTURE'
- **MF350-0327** — ANALYZED; CER=0.19444444444444445; detector findings=0
  - OCR: 'PRIVАTЕ\nBUDGET\nSYNTHETIO\nOСR\nFIXTURE'
- **MF350-0335** — ANALYZED; CER=0.14285714285714285; detector findings=0
  - OCR: 'SABOTAGE\nTEST\nSYNTHETIO\nOСR\nFIXTURE'
- **MF350-0340** — ANALYZED; CER=нет эталона; detector findings=0
  - OCR: 'CREDENTIAL\nTESТ\nSNTНETIС\nРDЕ\nFIХTURE'
- **MF350-0348** — ANALYZED; CER=0.7631578947368421; detector findings=0
  - OCR: 'HEIFТ\n1E1F1E\nITHTHETI\nF\nТEтТ'

## Артефакты

- `/home/user/mice-archives/ocr-benchmark-rapidocr.json`
- `/home/user/mice-archives/ocr-benchmark-paddleocr.json`
- `/home/user/mice-archives/ocr-deployed-tests.log`: 126 Django tests OK.
- Legacy pytest: 99 passed, 1 skipped, 5 failures in obsolete category_rules tests referencing removed app.categories.rules_for. Full legacy collection additionally references removed app.integrations and missing ML dependencies. Эти старые проверки не переписывались ради зелёного отчёта.

## Surya: обнаруженная проблема CPU

Образ 0.14.7 успешно собран, все веса проверены по SHA-256, контейнер запущен
на CPU во внутренней сети, health возвращает версию и локальные модели.
Первый реальный документ MF350-0304 не завершился в установленный лимит:
HTTP-запрос завершился ошибкой через 185.47 с. Это не успешное распознавание.
В процессе измерено приблизительно 4.76 GiB container memory (docker stats,
включает не только RSS процесса). Полный прогон на момент записи не завершён.
Поэтому CER/WER Surya не приведены. Нельзя рекомендовать этот CPU-провайдер
для рабочего потока на данном оборудовании без дополнительной оптимизации.
Провайдер по умолчанию остаётся RapidOCR. GPU не проверен.

Прогон Surya остановлен после двух последовательных таймаутов (185.47 и 187.37 с), чтобы не продолжать заведомо непроходящий CPU benchmark.
