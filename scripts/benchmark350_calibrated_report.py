"""Score only fresh live observations against the unchanged benchmark labels."""
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "test-data/results-benchmark350-ru3-calibrated"


def metric(tp, fp, fn):
    return dict(TP=tp, FP=fp, FN=fn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                F1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    rows = [json.loads(x) for x in (ROOT / "test-data/benchmark-350-v1/manifest.jsonl").read_text().splitlines()]
    obs = [json.loads(x) for x in (OUT / "observations.jsonl").read_text().splitlines()]
    assert len(rows) == len(obs) == len({o['id'] for o in obs}) == 350
    byid = {o['id']: o for o in obs}
    run = json.loads((OUT / "run.json").read_text())
    config = run['configuration']
    custom = {g['category']['id'] for g in config['groups']}
    categories = custom | {f['category'] for o in obs for f in o['analysis'].get('findings', [])}
    # Stable built-in catalog, including detectors with no findings.
    from app.detector_catalog import DETECTORS
    categories.update(c for _, _, ids in DETECTORS.values() for c in ids)
    expected_scope = {c for r in rows for c in r['expected_semantic_categories']}
    categories.update(expected_scope)
    counts = {c: collections.Counter(TP=0, FP=0, FN=0, TN=0) for c in categories}
    rules = {r['id']: {'category': g['category']['id'], 'title': r['title'],
             'TP': 0, 'FP': 0, 'unique_TP': 0, 'triggered_messages': 0}
             for g in config['groups'] for r in g['rules']}
    errors, messages, pipeline_errors = [], [], []
    policies = {p['id']: {"name": p['name'], "enabled": p['enabled'], "shadow": p['shadow'],
                "triggered_messages": 0, "expected_semantic_overlap": 0, "no_expected_semantic_overlap": 0}
                for p in run['policies']}
    stage_times = collections.defaultdict(list)
    for row in rows:
        o = byid[row['id']]
        assert hashlib.sha256((ROOT / 'test-data/benchmark-350-v1' / row['file']).read_bytes()).hexdigest() == o['sha256']
        findings = o['analysis'].get('findings', [])
        actual = {f['category'] for f in findings}
        expected = set(row['expected_semantic_categories'])
        for c in categories:
            counts[c]['TP' if c in actual and c in expected else 'FP' if c in actual else 'FN' if c in expected else 'TN'] += 1
        hit_rules = {f.get('rule_id') for f in findings} & rules.keys()
        for rid in hit_rules:
            rule = rules[rid]
            rule['triggered_messages'] += 1
            rule['TP' if rule['category'] in expected else 'FP'] += 1
            if rule['category'] in expected and sum(rules[r]['category'] == rule['category'] for r in hit_rules) == 1:
                rule['unique_TP'] += 1
        failures = [{'stage': j['kind'], 'error': j['error'], 'attempts': j['attempts']}
                    for j in o['pipeline_jobs'] if j['error'] or j['status'] == 'DEAD']
        if failures or o['analysis'].get('engine_errors'):
            pipeline_errors.append({'id': row['id'], 'jobs': failures, 'engine_errors': o['analysis'].get('engine_errors', [])})
        for j in o['pipeline_jobs']:
            if j['execution_seconds'] is not None:
                stage_times[j['kind']].append(j['execution_seconds'])
        for c in sorted((actual - expected) | (expected - actual)):
            fp = c in actual
            evidence = [f for f in findings if f['category'] == c]
            if fp:
                reason = ('Встроенный детектор отсутствует в семантической разметке; это расхождение с эталоном, '
                          'а не подтверждённая ложная находка.' if c not in custom else
                          'Правило сработало на приведённых фрагментах, но категория отсутствует в эталонной разметке; '
                          'контекст/локальное исключение не подавили срабатывание. Семантическая причина требует ручной экспертизы.')
            elif not o['evaluation_id']:
                reason = 'Конвейер не дошёл до свежей оценки политик: ' + json.dumps(failures, ensure_ascii=False)
            elif any(a['status'] != 'ANALYZED' for a in o['attachments']):
                reason = 'Есть неполностью извлечённое вложение; причинная связь с пропуском не доказана.'
            else:
                reason = 'Ни одно активное правило категории не сформировало находку на свежем тексте; конкретное невыполненное условие не трассируется штатным matcher.'
            errors.append({'id': row['id'], 'category': c, 'outcome': 'FP' if fp else 'FN',
                           'scenario': row['scenario'], 'reason': reason, 'evidence': evidence,
                           'attachment_statuses': [a['status'] for a in o['attachments']]})
        for hit in o['policy_hits']:
            pid = hit['policy_id']
            if pid in policies:
                p = policies[pid]
                p['triggered_messages'] += 1
                p['expected_semantic_overlap' if expected & {f['category'] for f in hit.get('findings', [])} else 'no_expected_semantic_overlap'] += 1
        messages.append({'id': row['id'], 'expected': sorted(expected), 'actual': sorted(actual),
            'FP': sorted(actual-expected), 'FN': sorted(expected-actual), 'seconds': o['seconds'],
            'fresh_evaluation': bool(o['evaluation_id']), 'policy_hits': o['policy_hits'], 'incident_id': o['incident_id']})
    def aggregate(scope):
        return metric(*(sum(counts[c][k] for c in scope) for k in ('TP','FP','FN')))
    def timing(values):
        values = sorted(values)
        return {'n': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
                'p95': values[min(len(values)-1, int(.95*len(values)))], 'min': min(values), 'max': max(values)} if values else {}
    per_category = {c: {**metric(*(counts[c][k] for k in ('TP','FP','FN'))), 'TN': counts[c]['TN'],
                       'label_scope': 'semantic' if c in expected_scope else 'unannotated_builtin'} for c in sorted(categories)}
    for r in rules.values():
        total = sum(rw['category'] == r['category'] for rw in rules.values())
        support = counts[r['category']]['TP'] + counts[r['category']]['FN']
        r.update(metric(r['TP'], r['FP'], support-r['TP']))
        r['category_rule_count'] = total
    summary = {'messages': 350, 'fresh_evaluations': sum(bool(o['evaluation_id']) for o in obs),
        'custom_micro': aggregate(custom), 'strict_all_categories': aggregate(categories),
        'per_category': per_category, 'statuses': dict(collections.Counter(o['status'] for o in obs)),
        'messages_with_pipeline_errors': len(pipeline_errors),
        'messages_with_policy_hits': sum(bool(o['policy_hits']) for o in obs),
        'messages_with_incident': sum(bool(o['incident_id']) for o in obs),
        'latency_seconds_including_queue': timing([o['seconds'] for o in obs]),
        'stage_execution_seconds': {k: timing(v) for k,v in stage_times.items()}}
    for name, value in [('metrics.json', summary), ('messages.json', messages), ('errors.json', errors),
                        ('rules.json', rules), ('policies.json', policies), ('pipeline-errors.json', pipeline_errors)]:
        save(name, value)
    def fmt(x):
        return '—' if x is None else f'{100*x:.2f}%'
    lines = ['# RU3 calibrated: live benchmark-350', '',
        '## Методика', '',
        f"Run `{run['run_id']}`, начало `{run['started_at']}`. 350 исходных EML, неизменённая авторская разметка benchmark-350-v1.",
        'Штатный приём и новые задания parse → extraction → OCR → detection → policy. Результаты прежнего анализа не использованы для оценки.',
        'ML, LLM, semantic отключены. Normalizer отключён. OCR: RapidOCR, enabled=true; настройки OCR не менялись.',
        'Правила не корректировались. Конфигурация и её снимки сохранены в run.json и observations.jsonl.', '',
        '## Ограничения интерпретации', '',
        'Эталон размечает семантические категории, не встроенные детекторы, отдельные правила или политики. '
        'Поэтому FP встроенных детекторов ниже — только строгие расхождения с отсутствующей разметкой, не доказанные ложные находки. '
        'Rule-level recall измерен относительно поддержки категории, не независимой разметки каждого правила. '
        'Для политик показаны фактические срабатывания; достоверные policy-level TP/FP/FN недоступны. '
        'Датасет уже использовался при калибровке, поэтому это не независимая оценка обобщения.', '',
        '## Итоги', '', json.dumps({k:v for k,v in summary.items() if k not in ('per_category','stage_execution_seconds')}, ensure_ascii=False, indent=2), '',
        '## Категории и встроенные детекторы', '',
        '| Категория | TP | FP | FN | Precision | Recall | F1 |', '|---|---:|---:|---:|---:|---:|---:|']
    for c,m in per_category.items():
        lines.append(f"| {c} | {m['TP']} | {m['FP']} | {m['FN']} | {fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['F1'])} |")
    lines += ['', '## Политики', '', '```json', json.dumps(policies, ensure_ascii=False, indent=2), '```', '',
              '## Эффективность правил', '', '| Правило | TP | FP | FN категории | Unique TP | Precision | Recall | F1 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rules.values():
        lines.append(f"| {r['title']} | {r['TP']} | {r['FP']} | {r['FN']} | {r['unique_TP']} | {fmt(r['precision'])} | {fmt(r['recall'])} | {fmt(r['F1'])} |")
    lines += ['', '## Время и ошибки', '', '```json', json.dumps(summary['stage_execution_seconds'], indent=2), '```',
              '', 'Полный журнал ошибок: pipeline-errors.json; все времена и попытки: observations.jsonl.', '',
              '## Все ошибочные обнаружения и пропуски', '']
    for e in errors:
        lines.append(f"- **{e['id']} {e['outcome']} {e['category']}** ({e['scenario']}): {e['reason']} "
                     + ('Evidence: `' + json.dumps(e['evidence'], ensure_ascii=False).replace('`', "'") + '`' if e['evidence'] else ''))
    (OUT / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('per_category','stage_execution_seconds')}, indent=2))


if __name__ == '__main__':
    main()