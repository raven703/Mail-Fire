"""Score frozen pipeline observations; never modifies detectors or trains models."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def score(expected, actual):
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    return collections.Counter(TP=tp, FP=fp, FN=fn)


def metrics(count):
    tp, fp, fn = (count[k] for k in ('TP', 'FP', 'FN'))
    return {**dict(count), 'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'F1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', type=Path)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    rows = [json.loads(x) for x in (args.corpus / 'manifest.jsonl').read_text().splitlines()]
    observed = [json.loads(x) for x in (args.results / 'observations.jsonl').read_text().splitlines()]
    byid = {r['id']: r for r in observed}
    assert len(byid) == len(observed) == len(rows) == 350
    config = json.loads((args.results / 'config.json').read_text())
    semantic = {c for r in rows for c in r['expected_semantic_categories']}
    categories = semantic | {c['id'] for c in config['categories']}
    categories |= {f['category'] for o in observed for f in o.get('analysis', {}).get('findings', [])}
    counts = {c: collections.Counter(TP=0, FP=0, FN=0, TN=0) for c in categories}
    records, extraction = [], []
    dimensions = {d: collections.defaultdict(collections.Counter) for d in
                  ('cohort', 'group', 'attachment_type', 'difficulty')}
    strict, scoped = collections.Counter(), collections.Counter()
    for row in rows:
        result = byid[row['id']]
        digest = hashlib.sha256((args.corpus / row['file']).read_bytes()).hexdigest()
        assert digest == result['sha256']
        expected = set(row['expected_semantic_categories'])
        actual = {f['category'] for f in result.get('analysis', {}).get('findings', [])}
        count = score(expected, actual)
        strict.update(count)
        scoped.update(score(expected, actual & semantic))
        for c in categories:
            counts[c]['TP' if c in expected and c in actual else 'FN' if c in expected
                      else 'FP' if c in actual else 'TN'] += 1
        for dim, value in [('cohort', row['id'][:5]), ('group', row['group']),
                           ('attachment_type', row['attachment_type']), ('difficulty', row['difficulty'])]:
            dimensions[dim][value].update(count)
            dimensions[dim][value]['messages'] += 1
        record = {**row, 'actual': sorted(actual), 'TP': sorted(expected & actual),
                  'FP': sorted(actual - expected), 'FN': sorted(expected - actual),
                  'exact': expected == actual, 'scoped_exact': expected == actual & semantic,
                  'message_id': result.get('message_id'), 'status': result.get('status', 'ERROR'),
                  'exception': result.get('exception'), 'seconds': result['seconds']}
        records.append(record)
        for attachment in result.get('attachments', []):
            expected_text = row.get('attachment_visible_text', '')
            text = attachment['text']
            def normalized(x):
                return ''.join(x.upper().split())
            extraction.append({'id': row['id'], 'type': row['attachment_type'], **attachment,
                               'expected_visible_text': expected_text,
                               'exact_visible_text': normalized(expected_text) in normalized(text)
                               if expected_text else None})
    summary = {'messages': 350, 'statuses': dict(collections.Counter(r['status'] for r in records)),
               'processing_exceptions': sum(bool(r['exception']) for r in records),
               'strict_all_categories': metrics(strict), 'semantic_scope_micro': metrics(scoped),
               'strict_exact': sum(r['exact'] for r in records),
               'semantic_scope_exact': sum(r['scoped_exact'] for r in records),
               'per_category': {c: metrics(n) for c, n in sorted(counts.items())},
               'dimensions': {d: {v: metrics(n) for v, n in values.items()}
                              for d, values in dimensions.items()},
               'attachment_statuses': dict(collections.Counter(a['status'] for a in extraction)),
               'attachment_count': len(extraction),
               'new_attachment_quality': {kind: {'total': len(items),
                     'visible_text_exact': sum(a['exact_visible_text'] is True for a in items)}
                     for kind in ('png', 'pdf')
                     for items in [[a for a in extraction if a['type'] == kind and a['expected_visible_text']]]},
               'caveats': ['Author-defined provisional semantic labels, not expert-adjudicated.',
                           'Strict auxiliary-category FP are not all confirmed semantic false alarms.',
                           'All 350 inputs included, including pipeline exceptions (no success-only filtering).',
                           'No active ML models; no training or detector tuning performed.']}
    for name, value in [('metrics', summary), ('messages', records), ('attachments', extraction)]:
        (args.results / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    for name, values in [('messages', records), ('attachments', extraction),
                         ('categories', [{'category': c, **m} for c, m in summary['per_category'].items()])]:
        keys = list(dict.fromkeys(k for r in values for k in r))
        with (args.results / (name + '.csv')).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                              for k, v in r.items()} for r in values)
    print(json.dumps({k: v for k, v in summary.items() if k not in ('per_category', 'dimensions')},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()