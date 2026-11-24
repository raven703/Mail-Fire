# Tesseract 5: неизменённые PNG benchmark350

## Среда и методика

tesseract 5.3.0; Debian bookworm, eng/rus; OEM=1; OMP_THREAD_LIMIT=1. Отдельный контейнер без сети, read-only rootfs, без production volumes. Рабочие OCR, БД, правила и модели не менялись. Обучение не выполнялось.

Каждый режим запущен 3 раза, текст повторов совпал. Время — медиана wall-clock, включая запуск CLI и загрузку модели. Время PaddleOCR в сохранённом baseline отсутствует; сравнение скорости с ним невозможно.

CER = Levenshtein / длина полного видимого эталона, включая watermark. Пробелы/переносы схлопываются; регистр и Unicode сохраняются, похожие кириллические/латинские буквы не исправляются. Цифровой идентификатор должен совпадать целиком с отдельной последовательностью цифр.

Важно: текущие EML 0319/0327/0335 были исправлены в предыдущем PR. Здесь извлечены как текущие MIME-байты (сравнимы с Paddle baseline), так и первоначальные байты из fea9bc68e00ea24b1cf76ff9f587fb86af284c39. Никакие PNG в этом тесте не пересоздавались, не улучшались и не заменялись. SHA-256 и пути — inputs.json. Для трёх изменённых исходных PNG сопоставимого сохранённого Paddle baseline нет.

Визуально проверен watermark: исходные bitmap-карточки содержат SYNTHETIC OCR TEST, исправленные ранее — SYNTHETIC OCR FIXTURE. Эталон учитывает это различие.

## Рекомендация

**Использовать оба как кандидатов для дальнейшей валидации; не заменять рабочий OCR по шести карточкам.** Tesseract Debian eng PSM 6 существенно лучше данного Paddle baseline (CER 9.13% против 37.50%), но не распознаёт исходный ИНН 0311 и паспорт 0348 точно ни в одном режиме. Текущий ИНН 0319 распознаётся полностью с PSM 6/11; PSM 7 не подходит этим двухстрочным изображениям. tessdata_best здесь хуже и медленнее Debian-моделей. Нельзя заявлять преимущество ансамбля на русском тексте: такого независимого теста не было.

Практический следующий шаг: отдельный dev-набор реальных сканов/русского текста и идентификаторов, затем проверка Tesseract как второго движка с явной фиксацией разногласий. Не исправлять цифры догадками и не выбирать режим по эталону в production.

## Сводка

|Группа|Движок/модель|Языки|PSM|Изображений|CER|Полный exact|ID exact|Среднее время, с|
|---|---|---|---:|---:|---:|---:|---:|---:|
|current|paddle_baseline/recorded|ru|None|6|37.50%|0|0/3|нет данных|
|current|tesseract/debian|eng|6|6|9.13%|3|1/3|0.1742|
|current|tesseract/debian|eng|7|6|56.73%|0|0/3|0.1471|
|current|tesseract/debian|eng|11|6|9.62%|3|1/3|0.1788|
|current|tesseract/debian|rus+eng|6|6|9.62%|3|1/3|0.2309|
|current|tesseract/debian|rus+eng|7|6|59.13%|0|0/3|0.1835|
|current|tesseract/debian|rus+eng|11|6|10.10%|3|1/3|0.2185|
|current|tesseract/best|eng|6|6|11.54%|3|1/3|0.2499|
|current|tesseract/best|eng|7|6|66.35%|0|0/3|0.1998|
|current|tesseract/best|eng|11|6|12.50%|3|1/3|0.2652|
|current|tesseract/best|rus+eng|6|6|13.94%|3|1/3|0.4180|
|current|tesseract/best|rus+eng|7|6|66.83%|0|0/3|0.3136|
|current|tesseract/best|rus+eng|11|6|14.90%|3|1/3|0.4333|
|initial_pr|paddle_baseline/recorded|ru|None|3|64.36%|0|0/2|нет данных|
|initial_pr|tesseract/debian|eng|6|6|13.85%|0|0/2|0.2089|
|initial_pr|tesseract/debian|eng|7|6|45.64%|0|0/2|0.1709|
|initial_pr|tesseract/debian|eng|11|6|18.46%|0|0/2|0.2070|
|initial_pr|tesseract/debian|rus+eng|6|6|19.49%|0|0/2|0.2745|
|initial_pr|tesseract/debian|rus+eng|7|6|45.64%|0|0/2|0.2279|
|initial_pr|tesseract/debian|rus+eng|11|6|21.54%|0|0/2|0.3417|
|initial_pr|tesseract/best|eng|6|6|20.51%|0|0/2|0.4292|
|initial_pr|tesseract/best|eng|7|6|51.28%|0|0/2|0.2511|
|initial_pr|tesseract/best|eng|11|6|25.64%|0|0/2|0.3439|
|initial_pr|tesseract/best|rus+eng|6|6|24.62%|0|0/2|0.5807|
|initial_pr|tesseract/best|rus+eng|7|6|57.95%|0|0/2|0.4022|
|initial_pr|tesseract/best|rus+eng|11|6|29.74%|0|0/2|0.5570|

## current

### MF350-0304

Эталон: `PUBLIC TEST / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|LEL ↵ TET ↵ IT'HTHETII ↵ F. ↵ TETT|50.00%|—|нет данных|
|tesseract/debian|eng|6|PUBLIC TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.1550|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1366|
|tesseract/debian|eng|11|PUBLIC TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.1542|
|tesseract/debian|rus+eng|6|PUBLIC TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.1966|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1570|
|tesseract/debian|rus+eng|11|PUBLIC TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.1809|
|tesseract/best|eng|6|FUBLIC TEST ↵ SYMTHETIC QCE TEST|13.33%|—|0.2333|
|tesseract/best|eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1617|
|tesseract/best|eng|11|FUELIC TES ↵  ↵ SYMTHETIC QCE TEST|20.00%|—|0.2375|
|tesseract/best|rus+eng|6|FUBLIC TEST ↵ SYMTHETIC ОСЕ TEST|16.67%|—|0.4023|
|tesseract/best|rus+eng|7|SYNTHETIC OCR TEST|40.00%|—|0.2596|
|tesseract/best|rus+eng|11|FUELIC TES ↵  ↵ SYMTHETIC ОСЕ TEST|23.33%|—|0.4652|

### MF350-0311

Эталон: `INN 7707083893 / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|гчгч ↵ ITEFEHIEIIEE ↵ ITHTHETII ↵ F. ↵ TE-T|72.73%|False|нет данных|
|tesseract/debian|eng|6|TNH rreresssas ↵ SYHTHETIC OCF TEST|42.42%|False|0.1642|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|45.45%|False|0.1349|
|tesseract/debian|eng|11|TNH rreresssas ↵  ↵ SYHTHETIC OCF TEST|42.42%|False|0.1800|
|tesseract/debian|rus+eng|6|ТНН rreresssas ↵ SYHTHETIC OCF TEST|45.45%|False|0.2410|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|45.45%|False|0.1959|
|tesseract/debian|rus+eng|11|ТНН rreresssas ↵  ↵ SYHTHETIC OCF TEST|45.45%|False|0.2936|
|tesseract/best|eng|6|IMM FPEvEE3E33 ↵ SYMTHETIC QCE TEST|39.39%|False|0.2724|
|tesseract/best|eng|7|SYNTHETIC DER TEST|51.52%|False|0.2021|
|tesseract/best|eng|11|IMM FPEvEE3E33 ↵  ↵ SYMTHETIC QCE TEST|39.39%|False|0.2645|
|tesseract/best|rus+eng|6|IMM РРНРаеЗеЗЗ ↵ SYMTHETIC ОСЕ TEST|48.48%|False|0.4714|
|tesseract/best|rus+eng|7|SYNTHETIC DER TEST|51.52%|False|0.2951|
|tesseract/best|rus+eng|11|IMM РРНРаеЗеЗЗ ↵  ↵ SYMTHETIC ОСЕ TEST|48.48%|False|0.4902|

### MF350-0319

Эталон: `INN 7707083893 / SYNTHETIC OCR FIXTURE`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|INN ↵ оо8383 ↵ SYNTHETIC ↵ OСR ↵ FIXTURE|19.44%|False|нет данных|
|tesseract/debian|eng|6|INN 7707083893 ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.1450|
|tesseract/debian|eng|7|syNTH mic och FOxTY RE|77.78%|False|0.1396|
|tesseract/debian|eng|11|INN 7707083893 ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.1615|
|tesseract/debian|rus+eng|6|INN 7707083893 ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.2046|
|tesseract/debian|rus+eng|7|Ут "СОС НТ, ВЕ|91.67%|False|0.1729|
|tesseract/debian|rus+eng|11|INN 7707083893 ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.2215|
|tesseract/best|eng|6|INN 7707083893 ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.2395|
|tesseract/best|eng|7|—_- re ooh FTL RE|83.33%|False|0.2309|
|tesseract/best|eng|11|INN 7707083893 ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.2584|
|tesseract/best|rus+eng|6|INN 7707083893 ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.4265|
|tesseract/best|rus+eng|7|о АТН пос FTL ВЕ|88.89%|False|0.3590|
|tesseract/best|rus+eng|11|INN 7707083893 ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|True|0.4107|

### MF350-0327

Эталон: `PRIVATE BUDGET / SYNTHETIC OCR FIXTURE`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|PRIVАTЕ ↵ BUDGET ↵ SYNTHETIO ↵ OСR ↵ FIXTURE|11.11%|—|нет данных|
|tesseract/debian|eng|6|PRIVATE BUDGET ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1513|
|tesseract/debian|eng|7|SYNTHETIC OCR TURE|50.00%|—|0.1321|
|tesseract/debian|eng|11|PRIVATE BUDGET ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1532|
|tesseract/debian|rus+eng|6|PRIVATE BUDGET ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1803|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TURE|50.00%|—|0.1650|
|tesseract/debian|rus+eng|11|PRIVATE BUDGET ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1912|
|tesseract/best|eng|6|PRIVATE BUDGET ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2417|
|tesseract/best|eng|7|CTH och Fun|86.11%|—|0.2005|
|tesseract/best|eng|11|PRIVATE BUDGET ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2570|
|tesseract/best|rus+eng|6|PRIVATE BUDGET ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.3489|
|tesseract/best|rus+eng|7|CTH оса Fun|86.11%|—|0.3061|
|tesseract/best|rus+eng|11|PRIVATE BUDGET ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.4091|

### MF350-0335

Эталон: `SABOTAGE TEST / SYNTHETIC OCR FIXTURE`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|SABOTAGE ↵ TEST ↵ SYNTHETIO ↵ OСR ↵ FIXTURE|5.71%|—|нет данных|
|tesseract/debian|eng|6|SABOTAGE TEST ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1624|
|tesseract/debian|eng|7|cenTHe ni oc i FIXTURE|65.71%|—|0.1474|
|tesseract/debian|eng|11|SABOTAGE TEST ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2001|
|tesseract/debian|rus+eng|6|SABOTAGE TEST ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2022|
|tesseract/debian|rus+eng|7|cenTHe ni oc i FIXTURE|65.71%|—|0.1769|
|tesseract/debian|rus+eng|11|SABOTAGE TEST ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.1804|
|tesseract/best|eng|6|SABOTAGE TEST ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2460|
|tesseract/best|eng|7|mc oc . FIXTURE|71.43%|—|0.2028|
|tesseract/best|eng|11|SABOTAGE TEST ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.2457|
|tesseract/best|rus+eng|6|SABOTAGE TEST ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.3385|
|tesseract/best|rus+eng|7|о ТЕТ ос и FIXTURE|68.57%|—|0.3358|
|tesseract/best|rus+eng|11|SABOTAGE TEST ↵  ↵ SYNTHETIC OCR FIXTURE|0.00%|—|0.3924|

### MF350-0348

Эталон: `PASSPORT 4510123456 / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|HEIFТ ↵ 1E1F1E ↵ ITHTHETI ↵ F ↵ ТEтТ|68.42%|False|нет данных|
|tesseract/debian|eng|6|PASSPORT 4516123456 ↵ SYHTHETIC OCF TEST|7.89%|False|0.2675|
|tesseract/debian|eng|7|SVATHETIC OCR TEST|57.89%|False|0.1919|
|tesseract/debian|eng|11|PASSPORT 4516123456 ↵  ↵ SYHTHETIC OCF TEST|7.89%|False|0.2240|
|tesseract/debian|rus+eng|6|PASSPORT 4516123456 ↵ SYHTHETIC OCF TEST|7.89%|False|0.3611|
|tesseract/debian|rus+eng|7|SVATHETIC OCR TEST|57.89%|False|0.2332|
|tesseract/debian|rus+eng|11|PASSPORT 4516123456 ↵  ↵ SYHTHETIC OCF TEST|7.89%|False|0.2435|
|tesseract/best|eng|6|FPRSSFORT 4518123456 ↵ SYMTHETIC QCE TEST|18.42%|False|0.2662|
|tesseract/best|eng|7|SUNTHETIC DLR TEST|60.53%|False|0.2009|
|tesseract/best|eng|11|FPRSSFORT 4518123456 ↵  ↵ SYMTHETIC QCE TEST|18.42%|False|0.3278|
|tesseract/best|rus+eng|6|FPRSSFORT 4519123456 ↵ SYMTHETIC ОСЕ TEST|21.05%|False|0.5203|
|tesseract/best|rus+eng|7|SUNTHETIC DLR TEST|60.53%|False|0.3259|
|tesseract/best|rus+eng|11|FPRSSFORT 4519123456 ↵  ↵ SYMTHETIC ОСЕ TEST|21.05%|False|0.4320|

## initial_pr

### MF350-0304

Эталон: `PUBLIC TEST / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|LEL ↵ TET ↵ IT'HTHETII ↵ F. ↵ TETT|50.00%|—|нет данных|
|tesseract/debian|eng|6|PUBLIC TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.1526|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1344|
|tesseract/debian|eng|11|PUBLIC TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.1557|
|tesseract/debian|rus+eng|6|PUBLIC TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.2012|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1696|
|tesseract/debian|rus+eng|11|PUBLIC TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.1972|
|tesseract/best|eng|6|FUBLIC TEST ↵ SYMTHETIC QCE TEST|13.33%|—|0.2593|
|tesseract/best|eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1859|
|tesseract/best|eng|11|FUELIC TES ↵  ↵ SYMTHETIC QCE TEST|20.00%|—|0.2418|
|tesseract/best|rus+eng|6|FUBLIC TEST ↵ SYMTHETIC ОСЕ TEST|16.67%|—|0.4065|
|tesseract/best|rus+eng|7|SYNTHETIC OCR TEST|40.00%|—|0.3389|
|tesseract/best|rus+eng|11|FUELIC TES ↵  ↵ SYMTHETIC ОСЕ TEST|23.33%|—|0.4934|

### MF350-0311

Эталон: `INN 7707083893 / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|гчгч ↵ ITEFEHIEIIEE ↵ ITHTHETII ↵ F. ↵ TE-T|72.73%|False|нет данных|
|tesseract/debian|eng|6|TNH rreresssas ↵ SYHTHETIC OCF TEST|42.42%|False|0.2470|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|45.45%|False|0.1640|
|tesseract/debian|eng|11|TNH rreresssas ↵  ↵ SYHTHETIC OCF TEST|42.42%|False|0.2184|
|tesseract/debian|rus+eng|6|ТНН rreresssas ↵ SYHTHETIC OCF TEST|45.45%|False|0.3391|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|45.45%|False|0.2824|
|tesseract/debian|rus+eng|11|ТНН rreresssas ↵  ↵ SYHTHETIC OCF TEST|45.45%|False|0.4577|
|tesseract/best|eng|6|IMM FPEvEE3E33 ↵ SYMTHETIC QCE TEST|39.39%|False|0.4498|
|tesseract/best|eng|7|SYNTHETIC DER TEST|51.52%|False|0.2765|
|tesseract/best|eng|11|IMM FPEvEE3E33 ↵  ↵ SYMTHETIC QCE TEST|39.39%|False|0.5573|
|tesseract/best|rus+eng|6|IMM РРНРаеЗеЗЗ ↵ SYMTHETIC ОСЕ TEST|48.48%|False|0.7326|
|tesseract/best|rus+eng|7|SYNTHETIC DER TEST|51.52%|False|0.5091|
|tesseract/best|rus+eng|11|IMM РРНРаеЗеЗЗ ↵  ↵ SYMTHETIC ОСЕ TEST|48.48%|False|0.7481|

### MF350-0319

Эталон: `PRIVATE BUDGET / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|tesseract/debian|eng|6|PRIVATE BUOGET ↵ SYHTHETIC OCF TEST|9.09%|—|0.2141|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|45.45%|—|0.2010|
|tesseract/debian|eng|11|PRIVATE BUOGET ↵  ↵ SYHTHETIC OCF TEST|9.09%|—|0.2341|
|tesseract/debian|rus+eng|6|PRIVATE ВУОБЕТ ↵ SYHTHETIC OCF TEST|24.24%|—|0.2869|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|45.45%|—|0.2309|
|tesseract/debian|rus+eng|11|PRIVATE ВУОБЕТ ↵  ↵ SYHTHETIC OCF TEST|24.24%|—|0.3749|
|tesseract/best|eng|6|FEIVATE ELOGET ↵ SYMTHETIC QCE TEST|24.24%|—|0.3884|
|tesseract/best|eng|7|CUNTHETIC OCR TEST|48.48%|—|0.2781|
|tesseract/best|eng|11|FEIVATE ELOGET ↵  ↵ SYMTHETIC QCE TEST|24.24%|—|0.3672|
|tesseract/best|rus+eng|6|FEIVATE ELOGET ↵ SYMTHETIC ОСЕ TEST|27.27%|—|0.8547|
|tesseract/best|rus+eng|7|CUNTHETIC OCR TEST|48.48%|—|0.4043|
|tesseract/best|rus+eng|11|FEIVATE ELOGET ↵  ↵ SYMTHETIC ОСЕ TEST|27.27%|—|0.5614|

PaddleOCR: сопоставимый baseline для этих исходных байтов отсутствует.

### MF350-0327

Эталон: `THREAT TEST / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|tesseract/debian|eng|6|THREAT TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.2489|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|40.00%|—|0.1994|
|tesseract/debian|eng|11|THREAT TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.2191|
|tesseract/debian|rus+eng|6|THREAT TEST ↵ SYHTHETIC OCF TEST|6.67%|—|0.3128|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|40.00%|—|0.2467|
|tesseract/debian|rus+eng|11|THREAT TES ↵  ↵ SYHTHETIC OCF TEST|10.00%|—|0.5049|
|tesseract/best|eng|6|THREEAT TEST ↵ SYMTHETIC QCE TEST|13.33%|—|0.6298|
|tesseract/best|eng|7|SUNTHETIE OCR TEST|46.67%|—|0.2764|
|tesseract/best|eng|11|THEEAT TES ↵  ↵ SYMTHETIC QCE TEST|16.67%|—|0.2952|
|tesseract/best|rus+eng|6|THREEAT TEST ↵ SYMTHETIC ОСЕ TEST|16.67%|—|0.4145|
|tesseract/best|rus+eng|7|СУМТНЕТТЕ OCR TEST|70.00%|—|0.3550|
|tesseract/best|rus+eng|11|THEEAT TES ↵  ↵ SYMTHETIC ОСЕ TEST|20.00%|—|0.4293|

PaddleOCR: сопоставимый baseline для этих исходных байтов отсутствует.

### MF350-0335

Эталон: `SECRET TOKEN / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|tesseract/debian|eng|6|SECRET TOKEH ↵ SYHTHETIC OCF TEST|9.68%|—|0.1735|
|tesseract/debian|eng|7|SYNTHETIC OCR TEST|41.94%|—|0.1502|
|tesseract/debian|eng|11|SE ↵  ↵ E ↵  ↵ SYHTHETIC OCF TEST|32.26%|—|0.1915|
|tesseract/debian|rus+eng|6|SECRET ТОКЕНЧ ↵ SYHTHETIC OCF TEST|25.81%|—|0.2340|
|tesseract/debian|rus+eng|7|SYNTHETIC OCR TEST|41.94%|—|0.2059|
|tesseract/debian|rus+eng|11|SE ↵  ↵ E ↵  ↵ SYHTHETIC OCF TEST|32.26%|—|0.2416|
|tesseract/best|eng|6|SECEET TOKEN ↵ SYMTHETIC QCE TEST|12.90%|—|0.5035|
|tesseract/best|eng|7|ZYMTRETIC LR TEST|58.06%|—|0.2303|
|tesseract/best|eng|11|SE ↵  ↵ E ↵  ↵ SYMTHETIC QCE TEST|35.48%|—|0.2490|
|tesseract/best|rus+eng|6|SECEET TOKEN ↵ SYMTHETIC ОСЕ TEST|16.13%|—|0.4957|
|tesseract/best|rus+eng|7|еУНТНЕТТО LR TEST|77.42%|—|0.4039|
|tesseract/best|rus+eng|11|SE ↵  ↵ E ↵  ↵ SYMTHETIC ОСЕ TEST|38.71%|—|0.4695|

PaddleOCR: сопоставимый baseline для этих исходных байтов отсутствует.

### MF350-0348

Эталон: `PASSPORT 4510123456 / SYNTHETIC OCR TEST`

|Движок/модель|Языки|PSM|Результат (↵ = перенос)|CER|ID exact|Время, с|
|---|---|---:|---|---:|---|---:|
|paddle_baseline/recorded|ru|None|HEIFТ ↵ 1E1F1E ↵ ITHTHETI ↵ F ↵ ТEтТ|68.42%|False|нет данных|
|tesseract/debian|eng|6|PASSPORT 4516123456 ↵ SYHTHETIC OCF TEST|7.89%|False|0.2175|
|tesseract/debian|eng|7|SVATHETIC OCR TEST|57.89%|False|0.1764|
|tesseract/debian|eng|11|PASSPORT 4516123456 ↵  ↵ SYHTHETIC OCF TEST|7.89%|False|0.2235|
|tesseract/debian|rus+eng|6|PASSPORT 4516123456 ↵ SYHTHETIC OCF TEST|7.89%|False|0.2731|
|tesseract/debian|rus+eng|7|SVATHETIC OCR TEST|57.89%|False|0.2316|
|tesseract/debian|rus+eng|11|PASSPORT 4516123456 ↵  ↵ SYHTHETIC OCF TEST|7.89%|False|0.2740|
|tesseract/best|eng|6|FPRSSFORT 4518123456 ↵ SYMTHETIC QCE TEST|18.42%|False|0.3444|
|tesseract/best|eng|7|SUNTHETIC DLR TEST|60.53%|False|0.2597|
|tesseract/best|eng|11|FPRSSFORT 4518123456 ↵  ↵ SYMTHETIC QCE TEST|18.42%|False|0.3527|
|tesseract/best|rus+eng|6|FPRSSFORT 4519123456 ↵ SYMTHETIC ОСЕ TEST|21.05%|False|0.5805|
|tesseract/best|rus+eng|7|SUNTHETIC DLR TEST|60.53%|False|0.4022|
|tesseract/best|rus+eng|11|FPRSSFORT 4519123456 ↵  ↵ SYMTHETIC ОСЕ TEST|21.05%|False|0.6405|

## Артефакты

results.json/csv: каждый режим, полный вывод, CER, идентификаторы, все три времени; summary.json: агрегаты; inputs.json: происхождение/SHA; environment.json: версии и SHA моделей; png/: текущие извлечённые PNG; png-initial-pr/: PNG первоначального PR. run.py и Dockerfile позволяют повторить тест. tessdata_best commit: e12c65a915945e4c28e237a9b52bc4a8f39a0cec; модели сохранены в /tmp/mice-tesseract-test/best.
