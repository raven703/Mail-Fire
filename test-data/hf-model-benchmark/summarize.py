"""Score saved predictions only; never tune thresholds or alter source labels."""
import csv
import json
from collections import Counter

from prepare import CORPUS, HERE, write_json
from run import RESULTS, read_jsonl, verify_frozen


def metric(tp, fp, fn, tn=None):
    return dict(tp=tp, fp=fp, fn=fn, tn=tn,
                precision=tp / (tp + fp) if tp + fp else 0.,
                recall=tp / (tp + fn) if tp + fn else 0.,
                f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.)


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    verify_frozen()
    protocol = json.loads((HERE / "protocol.json").read_text())
    audit = json.loads((RESULTS / "model_audit.json").read_text())
    manifest = {r["id"]: r for r in read_jsonl(CORPUS / "manifest.jsonl")}
    summary, errors, performance, statuses = [], [], {}, {}
    all_predictions = []
    context_errors = Counter()
    for key, info in audit.items():
        status_file = RESULTS / f"{key}-status.json"
        status = json.loads(status_file.read_text()) if status_file.exists() else {"status": "not_run"}
        statuses[key] = status
        perf = RESULTS / f"{key}-performance.json"
        performance[key] = json.loads(perf.read_text()) if perf.exists() else dict(status=status["status"])
        predictions = RESULTS / f"{key}-predictions.jsonl"
        if status["status"] != "completed":
            continue
        rows = read_jsonl(predictions)
        assert {r["id"] for r in rows} == set(manifest) and len(rows) == len(manifest)
        all_predictions.extend(rows)
        if key == "redmadrobot":
            continue
        for category in rows[0]["scores"]:
            # Also report extraction-complete subset, retaining all errors in full cohort.
            for scope in ("B350_all", "B350_extraction_complete"):
                counts = Counter()
                selected = [r for r in rows if scope == "B350_all" or not r["extraction_errors"]]
                threshold = protocol["threat_threshold"] if key == "gloomreach" else protocol["classification_threshold"]
                for prediction in selected:
                    expected = manifest[prediction["id"]]
                    definition = protocol["categories"][category]
                    truth = bool(expected["expected_no_issue"]) if definition.get("truth_no_issue") else bool(set(expected["expected_semantic_categories"]) & set(definition["truth_any"]))
                    score = prediction["scores"][category]
                    positive = score >= threshold
                    outcome = "tp" if truth and positive else "fn" if truth else "fp" if positive else "tn"
                    counts[outcome] += 1
                    if outcome in {"fp", "fn"} and scope == "B350_all":
                        errors.append(dict(model=key, category=category, id=prediction["id"], outcome=outcome,
                            score=score, threshold=threshold, scenario=expected["scenario"], group=expected["group"],
                            attachment_type=expected["attachment_type"], extraction_limited=bool(prediction["extraction_errors"])))
                        context_errors[(key, category, expected["scenario"], outcome)] += 1
                summary.append(dict(model=key, category=category, scope=scope, n=len(selected), threshold=threshold,
                                    **metric(*(counts[k] for k in ("tp", "fp", "fn", "tn")))))
    fixture_path = RESULTS / "ner-fixture-predictions.json"
    if fixture_path.exists():
        fixture = json.loads((HERE / "ner_fixture.json").read_text())
        predictions = {p["id"]: p for p in json.loads(fixture_path.read_text())}
        for label in fixture["metric_scope"]:
            tp = fp = fn = 0
            for example in fixture["examples"]:
                expected = set()
                for kind, value in example["entities"]:
                    assert example["text"].count(value) == 1
                    if kind == label:
                        start = example["text"].index(value)
                        expected.add((start, start + len(value)))
                actual = {(e["start"], e["end"]) for e in predictions[example["id"]]["entities"] if e["label"] == label}
                tp += len(actual & expected)
                fp += len(actual - expected)
                fn += len(expected - actual)
            summary.append(dict(model="redmadrobot", category=label, scope="AI_authored_NER_fixture_not_independent_gold",
                                n=len(fixture["examples"]), threshold="BIO_argmax", **metric(tp, fp, fn)))
    write_csv(RESULTS / "summary.csv", summary, ["model", "category", "scope", "n", "threshold", "tp", "fp", "fn", "tn", "precision", "recall", "f1"])
    write_csv(RESULTS / "errors.csv", errors, ["model", "category", "id", "outcome", "score", "threshold", "scenario", "group", "attachment_type", "extraction_limited"])
    with (RESULTS / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for prediction in all_predictions:
            stream.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    write_json(RESULTS / "performance.json", performance)
    write_json(RESULTS / "statuses.json", statuses)
    lines = ["# Независимый GPU-бенчмарк Hugging Face / B-350", "", "## Условия и статус", "",
             "Дата: 27 ноября 2026. Ничего не обучалось; рабочий MICE и исходные EML/manifest не изменены.",
             "Отдельное venv, CUDA RTX 4060; только FP32, FP16 не использовался. Модели выполнялись последовательно в отдельных процессах.",
             "Ревизии, лицензии, labels, версии и GPU: `environment.json`, `model_audit.json`.",
             "Протокол, все 350 ID и hashes зафиксированы отдельным коммитом до инференса.", "",
             "| Модель | Статус | Лицензия |", "|---|---|---|"]
    for key, info in audit.items():
        lines.append(f"| {info['repo']} | {statuses[key]['status']} | {info.get('license', 'unknown')} |")
    lines += ["", "## Методика и ограничения", "",
        "- Все 350 писем классифицируются одинаковым текстом: subject, MIME body и доступные вложения. Контроли, учебные примеры, цитаты и пересылки не исключаются.",
        "- DOCX/XLSX извлечены непосредственно из ZIP/XML; HTML очищен; TXT/CSV декодированы; PDF через pypdf. Manifest используется только как ground truth, не как источник текста вложений.",
        "- OCR Tesseract отсутствует: 6 PNG-вложений не распознаны. Письма остаются в полном прогоне; ошибки помечены extraction_limited. Есть дополнительные метрики на extraction-complete subset. Это не доказывает, что каждую ошибку вызвал OCR.",
        "- Window 900 символов, overlap 100; максимум 512 токенов. Максимум вероятности по окнам усиливает как recall, так и FP. Сохраняются logits, полные классовые вероятности, усечения и provenance.",
        "- NLI: одинаковые английские гипотезы, independent entailment-vs-contradiction softmax (neutral mDeBERTa не входит в знаменатель). Порог 0.5 до smoke. Нормализации между категориями нет, safe может пересекаться с другими ответами.",
        "- Семантические категории — фиксированные proxies из protocol.json: коммерция=pricing, финансы=financial-plans; exfiltration включает SECRET/credentials. Они не охватывают все возможные значения понятий. Safe оценивается по авторскому expected_no_issue.",
        "- Phishing: softmax Phishing=0, Legit=1, threshold 0.5. Gloomreach: три sigmoid головы; только threat сопоставляется с violence/explosive, threshold 0.4 из upstream config; profanity/illegal без gold не оцениваются.",
        "- B-350 не содержит эталонных entity spans: NER на B-350 только качественный, без TP/FP/FN. Нет требования находить организации моделью redmadrobot, где такого класса нет.",
        "- Малый отдельный NER fixture с вручную указанными в файле spans создан AI, а не независимым человеком. Его exact-span метрики — только проверка механики, не независимое качество. Требуется человеческая проверка границ и более широкий корпус, включая адреса/организации согласно поддерживаемым классам.",
        "- ИНН/СНИЛС/паспорт остаются задачей алгоритмических детекторов. NER-метрики по ним не выставлялись.",
        "- ScienceSoft: опубликован только int8 CPU-oriented ONNX; GPU/Transformers smoke и основной прогон не выполнялись, CPU fallback и конвертация весов запрещены протоколом. ONNX Runtime CUDA provider отдельно не исследовался: это ограничение данного запуска, а не доказательство невозможности любого GPU backend. Лицензия разрешает воспроизводить оценку, но не production/модификацию/redistribution.",
        "- Gloomreach: локальная reviewed реализация опубликованной архитектуры, weights_only=True и strict=True для полного checkpoint. Никакой удалённый Python не исполнялся, случайных недостающих голов не допускается.",
        "- Первый Gloomreach load остановился до smoke: checkpoint оказался обёрткой с model_state_dict/epoch/val_loss/class_weights, а не голым state_dict. Исправлен только reader обёртки; 61 ключ полного encoder/трёх голов проверены strict=True. Исходная ошибка сохранена в gloomreach-initial-load-error.json. Retry выполнен после завершения остальных GPU-процессов, протокол/пороги/веса не менялись.",
        "- Aleksandr505: лицензия не указана; production требует отдельного правового согласования.",
        "- B-350 синтетический, авторски размеченный. Это не доказательство производственной точности и не независимый человеческий NER benchmark.", "", "## Классификация: полный B-350", "",
        "Сравнивать только одинаковую категорию/выборку, не общий F1 NER и классификаторов.", "",
        "| Модель | Категория | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in summary:
        if row["scope"] == "B350_all":
            lines.append(f"| {row['model']} | {row['category']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |")
    indexed = {(r["model"], r["category"]): r for r in summary if r["scope"] == "B350_all"}
    lines += ["", "### Сопоставимые модели и практические рекомендации", ""]
    for category in protocol["categories"]:
        pair = [indexed.get((m, category)) for m in ("horizon", "mdeberta")]
        if all(pair):
            first, second = pair
            lines.append(f"- {category}: Horizon F1={first['f1']:.3f}, FP={first['fp']}, FN={first['fn']}; mDeBERTa F1={second['f1']:.3f}, FP={second['fp']}, FN={second['fn']}. Только эта категория и общий cohort сопоставимы.")
    for model, category in (("gloomreach", "threat"), ("phishing", "phishing")):
        record = indexed.get((model, category))
        if record:
            lines.append(f"- Профильный {model}/{category}: F1={record['f1']:.3f}, FP={record['fp']}, FN={record['fn']}; сравнивается только с NLI-строками {category}.")
    if ("gloomreach", "threat") in indexed:
        lines.append("- Gloomreach threat в этом протоколе не обнаружил ни одного положительного B-350 примера: не рекомендован как единственный threat detector. Это не оценка profanity/illegal и не доказательство качества вне данного домена. Upstream пример использует 128-token truncation; здесь заранее зафиксирована общая оконная схема 512 tokens, что также ограничивает перенос выводов.")
    if ("phishing", "phishing") in indexed:
        lines.append("- Специализированный phishing RuBERT уступил Horizon по phishing F1 на том же cohort и пороге, но превысил mDeBERTa при этих гипотезах. Нельзя переносить это на иные корпуса/лицензионные условия.")
    lines += ["", "При данном фиксированном протоколе Horizon — кандидат для дальнейшей проверки financial, но не готовая универсальная DLP-модель. Высокая precision при низком recall на отдельных категориях не означает полноту защиты.",
        "mDeBERTa в текущей формулировке phishing/exfiltration требует особенно тщательной проверки FP. Это результат конкретных гипотез/порога/корпуса, не доказательство общего превосходства архитектуры Horizon.",
        "Обе NLI-модели могут не выбирать safe: это самостоятельная гипотеза, а не автоматическое отрицание остальных классов. Нулевой safe F1 при этом протоколе не означает, что все безопасные письма помечены опасными.",
        "Redmadrobot можно рассматривать только как кандидат на entity extraction после человеческой span-разметки, не как DLP-policy classifier. ScienceSoft не подходит для запрошенного неизменённого PyTorch/CUDA запуска; production также не разрешён опубликованными условиями. Phishing-кандидат требует выяснения лицензии."]
    lines += ["", "## NER: только отдельный AI-authored fixture", "",
              "Не сравнивать эти exact-span показатели с document-level F1 B-350. Организации/адресные компоненты вне metric_scope не получают ложный нулевой F1.",
              "| Тип | TP | FP | FN | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in summary:
        if row["scope"] == "AI_authored_NER_fixture_not_independent_gold":
            lines.append(f"| {row['category']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |")
    lines += ["", "## Источники", ""]
    for key, info in audit.items():
        if info.get("card_url"):
            lines.append(f"- [{info['repo']}]({info['card_url']}): config.json той же ревизии, штатные labels и условия model card; SHA сохранён в environment.")
    lines += ["", "## Производительность", "", "| Модель | Время основного прогона, с | Писем/с | Peak RAM GiB | Peak allocated VRAM GiB |", "|---|---:|---:|---:|---:|"]
    for key, perf in performance.items():
        if "main_seconds" in perf:
            lines.append(f"| {key} | {perf['main_seconds']:.2f} | {perf['messages_per_second']:.2f} | {perf['peak_process_rss_bytes']/2**30:.2f} | {perf['peak_vram_allocated_bytes']/2**30:.2f} |")
    lines += ["", "RAM sampled 20ms; VRAM allocated/reserved — process PyTorch allocator, не desktop VRAM. Loading/download excluded from throughput; serialization/windowing included. NER timing includes small fixture. No cross-task speed ranking.",
              "", "## Ошибки сложных контекстов", "", "Полный errors.csv сохраняет ID, scenario, group, attachment type и признак extraction limitation. Ни один ошибочный пример не исключён.", ""]
    hard = [(key, n) for key, n in context_errors.items() if any(term in key[2] for term in ("training", "quote", "discussion", "fake", "public"))]
    for (model, cat, scenario, outcome), count in sorted(hard):
        lines.append(f"- {model}/{cat}: {scenario}, {outcome.upper()}={count}.")
    lines += ["", "## Выводы и дальнейшая проверка", "",
        "Для сравнения Horizon и mDeBERTa используйте строки одной категории; для phishing/threat добавляйте профильную модель только в той же колонке. Универсальная суммарная оценка шести моделей намеренно отсутствует.",
        "Ни одна модель не утверждается как production-ready. Кандидат на отдельную проверку должен показать приемлемый FP на независимой реальной/экспертно размеченной выборке и пройти анализ лицензии, latency, обфускации, длинных цепочек и вложений.",
        "Утверждать, какие модели хуже действующих MICE-детекторов, нельзя: сопоставимого изолированного baseline в этом эксперименте нет, рабочая система не запускалась. Готовые detector outputs не использованы как признаки. Алгоритмические форматные детекторы не заменяются NER.",
        "Следующий шаг: независимая человеческая NER-разметка, полный OCR, matched baseline MICE на отдельном согласованном стенде, затем отдельный calibration split (не B-350). Никакой интеграции или автоматической публикации.", ""]
    (RESULTS / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Summary rows", len(summary), "errors", len(errors), "predictions", len(all_predictions))


if __name__ == "__main__":
    main()