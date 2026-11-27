"""Development-only exhaustive decision grid and deterministic selection."""
import itertools

import numpy as np
from common import DATA, HERE, load, metrics, rows, save, sha

THRESHOLDS = [round(.1 + .05 * i, 2) for i in range(18)]
AGGREGATIONS = ['max', 'mean', 'top2_mean', 'noisy_or']


def candidates():
    for i in range(6):
        yield dict(hypotheses=[f'h{i}'], combine='single')
    for a, b in itertools.combinations(range(6), 2):
        for mode in ['mean', 'max', 'min']:
            yield dict(hypotheses=[f'h{a}', f'h{b}'], combine=mode)
    yield dict(hypotheses=[f'h{i}' for i in range(6)], combine='mean')
    for i in range(6):
        for j in (6, 7):
            for mode in ['subtract', 'product']:
                yield dict(hypotheses=[f'h{i}', f'h{j}'], combine=mode)


def calculate(matrix, order, category, cfg):
    indices = [next(i for i, o in enumerate(order) if o[0] == category and o[1] == h) for h in cfg['hypotheses']]
    values = np.asarray(matrix, dtype=np.float64)[:, indices]
    mode = cfg['combine']
    if mode == 'single':
        chunk = values[:, 0]
    elif mode == 'mean':
        chunk = values.mean(axis=1)
    elif mode == 'max':
        chunk = values.max(axis=1)
    elif mode == 'min':
        chunk = values.min(axis=1)
    elif mode == 'subtract':
        chunk = np.maximum(0, values[:, 0] - values[:, 1])
    elif mode == 'product':
        chunk = values[:, 0] * (1 - values[:, 1])
    else:
        raise ValueError(mode)
    aggregation = cfg['aggregation']
    if aggregation == 'max':
        return float(chunk.max())
    if aggregation == 'mean':
        return float(chunk.mean())
    if aggregation == 'top2_mean':
        return float(np.sort(chunk)[-2:].mean())
    if aggregation == 'noisy_or':
        return float(1 - np.prod(1 - chunk))
    raise ValueError(aggregation)


def main():
    assert not (HERE / 'freeze.json').exists(), 'Cannot tune after freeze'
    spec = load(HERE / 'hypotheses.json')
    labels = rows(DATA / 'b350-labels.jsonl') + rows(DATA / 'b400-labels.jsonl')
    ids = [r['id'] for r in labels]
    dtype_results, all_candidates = {}, []
    for dtype in ('fp32', 'fp16'):
        for corpus in ('b350', 'b400'):
            assert (DATA / f'{corpus}-{dtype}/COMPLETE').exists()
        cached = rows(DATA / f'b350-{dtype}/scores.jsonl') + rows(DATA / f'b400-{dtype}/scores.jsonl')
        assert [r['id'] for r in cached] == ids
        order = load(DATA / f'b350-{dtype}/metadata.json')['order']
        dtype_results[dtype] = {}
        for category in spec['categories']:
            y = [category in r['expected'] for r in labels]
            best, singles, ensembles, exclusions = None, None, None, None
            for candidate in candidates():
                for aggregation in AGGREGATIONS:
                    cfg = dict(**candidate, aggregation=aggregation)
                    scores = [calculate(r['scores'], order, category, cfg) for r in cached]
                    for threshold in THRESHOLDS:
                        m = metrics(y, [s >= threshold for s in scores])
                        result = dict(**cfg, threshold=threshold, development=m)
                        # Prefer high F1, then fewer FP, fewer hypotheses, higher threshold;
                        # remaining ties retain the explicitly enumerated first candidate.
                        key = (m['F1'], -m['FP'], -len(candidate['hypotheses']), threshold)
                        if best is None or key > best[0]:
                            best = (key, result)
                        family = 'single' if candidate['combine'] == 'single' else 'exclusion' if candidate['combine'] in ('subtract', 'product') else 'ensemble'
                        current = {'single': singles, 'ensemble': ensembles, 'exclusion': exclusions}[family]
                        if current is None or key > current[0]:
                            if family == 'single':
                                singles = (key, result)
                            elif family == 'ensemble':
                                ensembles = (key, result)
                            else:
                                exclusions = (key, result)
                        all_candidates.append(dict(dtype=dtype, category=category, family=family, **result))
            dtype_results[dtype][category] = dict(best=best[1], single=singles[1], ensemble=ensembles[1], exclusion=exclusions[1])
            print(dtype, category, best[1], flush=True)
    # FP32 is preregistered reference. FP16 remains a locked numeric/performance ablation.
    config = dict(dtype='fp32', revision=load(DATA / 'b350-fp32/metadata.json')['revision'],
        categories={c: v['best'] for c, v in dtype_results['fp32'].items()},
        selection='Max pooled B350+B400 F1; ties fewer FP, fewer hypotheses, higher threshold, enumeration order',
        thresholds=THRESHOLDS, window_characters=900, overlap=100, max_tokens=512,
        multilabel='Independent category score >= category threshold; no cross-category softmax',
        fp16_policy='Same FP32-selected rules on B500; FP16 development optimum is diagnostic only')
    save(HERE / 'best_config.json', config)
    save(HERE / 'development-best.json', dtype_results)
    import gzip
    import json
    with gzip.open(HERE / 'development-grid.jsonl.gz', 'xt', encoding='utf-8') as stream:
        for result in all_candidates:
            stream.write(json.dumps(result) + '\n')
    save(HERE / 'freeze.json', dict(best_config_sha256=sha((HERE / 'best_config.json').read_bytes()),
        hypotheses_sha256=sha((HERE / 'hypotheses.json').read_bytes()),
        development={c: {d: sha((DATA / f'{c}-{d}/scores.jsonl').read_bytes()) for d in ('fp32', 'fp16')} for c in ('b350', 'b400')},
        protocol='All selected rules fixed before first B500 preparation/inference. B500 previously used by MICE, not a virgin corpus.',
        decision_order='Combine hypotheses inside each window, then aggregate windows; exclusions apply locally',
        scripts={p.name: sha(p.read_bytes()) for p in HERE.glob('*.py')}))


if __name__ == '__main__':
    main()