"""Recalculate all evaluation metrics from caches, without CUDA or retuning."""
import base64
import csv
import gzip
import json

import numpy as np
from common import DATA, HERE, INPUTS, average_precision, load, metrics, rows, save, sha
from optimize import calculate


def aggregate(labels, predicted, scores, categories):
    per = {}
    safe = [i for i, r in enumerate(labels) if not r['expected']]
    for c in categories:
        y = [c in r['expected'] for r in labels]
        p = [c in r for r in predicted]
        per[c] = dict(**metrics(y, p), PR_AUC_AP=average_precision(y, [r[c] for r in scores]),
                      safe_messages=len(safe), safe_FP=sum(p[i] for i in safe),
                      safe_FP_rate=sum(p[i] for i in safe) / len(safe) if safe else None)
    flat_y = [c in r['expected'] for r in labels for c in categories]
    flat_p = [c in p for p in predicted for c in categories]
    return dict(micro=metrics(flat_y, flat_p), macro_F1=float(np.mean([m['F1'] for m in per.values()])),
                safe_messages=len(safe), safe_messages_with_FP=sum(bool(predicted[i]) for i in safe),
                safe_message_FP_rate=sum(bool(predicted[i]) for i in safe) / len(safe) if safe else None,
                per_category=per)


def main():
    config = load(HERE / 'best_config.json')
    categories = list(config['categories'])
    summary, errors, predictions, evaluations, performance = [], [], [], {}, {}
    texts = {c: {r['id']: r['text'] for r in rows(DATA / f'{c}-texts.jsonl')} for c in ('b350', 'b400', 'b500')}
    for corpus in ('b350', 'b400', 'b500'):
        labels = rows(DATA / f'{corpus}-labels.jsonl')
        for dtype in ('fp32', 'fp16'):
            cache = DATA / f'{corpus}-{dtype}'
            assert (cache / 'COMPLETE').exists()
            cached = rows(cache / 'scores.jsonl')
            assert [r['id'] for r in cached] == [r['id'] for r in labels]
            order = load(cache / 'metadata.json')['order']
            scores = [{c: calculate(r['scores'], order, c, config['categories'][c]) for c in categories} for r in cached]
            actual = [[c for c in categories if s[c] >= config['categories'][c]['threshold']] for s in scores]
            result = aggregate(labels, actual, scores, categories)
            evaluations[f'{corpus}-{dtype}'] = result
            for c, m in result['per_category'].items():
                summary.append(dict(corpus=corpus, dtype=dtype, category=c, **m,
                    threshold=config['categories'][c]['threshold'],
                    hypotheses='+'.join(config['categories'][c]['hypotheses']),
                    combine=config['categories'][c]['combine'], aggregation=config['categories'][c]['aggregation']))
            slices = {}
            for group in sorted({r['group'] for r in labels}):
                indices = [i for i, r in enumerate(labels) if r['group'] == group]
                slices[f'group:{group}'] = aggregate([labels[i] for i in indices], [actual[i] for i in indices], [scores[i] for i in indices], categories)
            for name, condition in [('length:<=900', lambda n: n <= 900), ('length:901-1800', lambda n: 900 < n <= 1800), ('length:>1800', lambda n: n > 1800)]:
                indices = [i for i, r in enumerate(cached) if condition(r['characters'])]
                if indices:
                    slices[name] = dict(messages=len(indices), **aggregate([labels[i] for i in indices], [actual[i] for i in indices], [scores[i] for i in indices], categories))
            result['slices'] = slices
            perf = load(cache / 'performance.json')
            times = [r['seconds'] for r in cached]
            performance[f'{corpus}-{dtype}'] = dict(messages=len(times), hypotheses=len(order),
                seconds=perf['seconds'], mean_seconds=float(np.mean(times)), p50_seconds=float(np.median(times)),
                p95_seconds=float(np.percentile(times, 95)), messages_per_second=len(times) / sum(times),
                **{k: v for k, v in perf.items() if k.startswith('peak_')}, scope=perf['scope'])
            for i, (label, score, pred) in enumerate(zip(labels, scores, actual)):
                predictions.append(dict(corpus=corpus, dtype=dtype, id=label['id'],
                    text_sha256=cached[i]['text_sha256'], expected=label['expected'], actual=pred, scores=score,
                    seconds=cached[i]['seconds'], characters=cached[i]['characters']))
                for c in set(label['expected']) ^ set(pred):
                    if c not in categories:
                        continue
                    errors.append(dict(corpus=corpus, dtype=dtype, id=label['id'], category=c,
                        error='FP' if c in pred else 'FN', score=score[c],
                        threshold=config['categories'][c]['threshold'], group=label['group'],
                        text=texts[corpus][label['id']], extraction_status=label['extraction_status']))
    # Compare against frozen historical results. No detector is called.
    labels = rows(DATA / 'b500-labels.jsonl')
    expected = {r['id']: sorted(r['expected']) for r in labels}
    ml = INPUTS / 'ml/test-data/results-ml-category-benchmark'
    comparisons, checks = {}, {}
    source_obs = INPUTS / 'baseline/test-data/results-benchmark500-v1/observations.jsonl'
    historical_experiment = load(ml / 'experiment.json')
    assert sha(source_obs.read_bytes()) == historical_experiment['input_hashes']['b500']['observations_sha256']
    for engine in ('ru3', 'ru4', 'tfidf', 'setfit', 'rubert'):
        if engine in ('ru3', 'ru4'):
            file = INPUTS / f'baseline/test-data/results-benchmark500-v1/{engine}/messages.json'
            historical = load(file)
        else:
            file = ml / f'{engine}-b500/messages.json.gz.b64'
            historical = json.loads(gzip.decompress(base64.b64decode(file.read_bytes())))
        assert len(historical) == 500 and set(r['id'] for r in historical) == set(expected)
        assert all(sorted(r['expected']) == expected[r['id']] for r in historical)
        by_id = {r['id']: r for r in historical}
        actual = [by_id[r['id']]['actual'] for r in labels]
        zero = [{c: 0 for c in categories} for _ in labels]
        comparisons[engine] = aggregate(labels, actual, zero, categories)
        # No historical AP claims: scores unavailable/not comparable for every engine.
        for m in comparisons[engine]['per_category'].values():
            del m['PR_AUC_AP']
        checks[engine] = dict(messages=500, category_scope=categories, labels_equal=True,
            predictions_sha256=sha(file.read_bytes()),
            text_evidence='Exact observations.jsonl SHA256 equals ML experiment input_hashes.b500; labels and all 500 IDs verified; model scripts read observation text',
            caveat='Historical artifacts not rerun; conditional comparison, not an independently reproduced baseline')
    save(HERE / 'comparison.json', dict(metrics=comparisons, checks=checks,
        observations_sha256=sha(source_obs.read_bytes()),
        b500_manifest_equal=sha((INPUTS / 'b500/test-data/benchmark-500-v1/manifest.jsonl').read_bytes()) == sha((INPUTS / 'baseline/test-data/benchmark-500-v1/manifest.jsonl').read_bytes())))
    for dtype in ('fp32', 'fp16'):
        folder = DATA / f'speed-{dtype}'
        if (folder / 'COMPLETE').exists():
            perf = load(folder / 'performance.json')
            groups = {}
            for n in (12, 24, 48, 96):
                times = [r['seconds'] for r in perf['timings'] if r['hypotheses'] == n]
                groups[str(n)] = dict(mean_seconds=float(np.mean(times)), p50_seconds=float(np.median(times)),
                    p95_seconds=float(np.percentile(times, 95)), messages_per_second=1 / float(np.mean(times)), observations=len(times))
            performance[f'speed-{dtype}'] = dict(groups=groups, **{k: v for k, v in perf.items() if k.startswith('peak_')})
    a = [r for r in predictions if r['corpus'] == 'b500' and r['dtype'] == 'fp32']
    b = [r for r in predictions if r['corpus'] == 'b500' and r['dtype'] == 'fp16']
    performance['fp16_quality_delta'] = dict(changed_decisions=sum((c in x['actual']) != (c in y['actual']) for x, y in zip(a, b) for c in categories),
        max_score_delta=max(abs(x['scores'][c] - y['scores'][c]) for x, y in zip(a, b) for c in categories),
        micro_F1=evaluations['b500-fp16']['micro']['F1'] - evaluations['b500-fp32']['micro']['F1'])
    save(HERE / 'evaluation.json', evaluations)
    save(HERE / 'performance.json', performance)
    for filename, values in [('summary.csv', summary), ('errors.csv', errors)]:
        with (HERE / filename).open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    with (HERE / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
        for value in predictions:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    print('Reported', len(predictions), 'predictions;', len(errors), 'category errors')


if __name__ == '__main__':
    main()