"""Verify saved metrics, inputs, freeze ordering and immutable raw-cache archives."""
import csv
import gzip
import subprocess

from common import DATA, HERE, INPUTS, ROOT, load, metrics, rows, sha


def main():
    freeze_commit = '5caf41e32049d39b0e46e0843152b4529478626a'
    freeze = load(HERE / 'freeze.json')
    assert sha((HERE / 'best_config.json').read_bytes()) == freeze['best_config_sha256']
    assert sha((HERE / 'hypotheses.json').read_bytes()) == freeze['hypotheses_sha256']
    committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{freeze_commit}:test-data/horizon-benchmark/freeze.json'])
    assert sha(committed) == sha((HERE / 'freeze.json').read_bytes())
    for c in ('b350', 'b400', 'b500'):
        prov = load(HERE / f'{c}-provenance.json')
        assert sha((DATA / f'{c}-texts.jsonl').read_bytes()) == prov['texts_sha256']
        assert sha((DATA / f'{c}-labels.jsonl').read_bytes()) == prov['labels_sha256']
        corpus = ROOT / 'test-data/benchmark-350-v1' if c == 'b350' else INPUTS / f'{c}/test-data/benchmark-{c[1:]}-v1'
        assert sha((corpus / 'manifest.jsonl').read_bytes()) == prov['manifest_sha256']
        for path, expected in prov['source_eml_sha256'].items():
            assert sha((corpus / path).read_bytes()) == expected
        for dtype in ('fp32', 'fp16'):
            folder = DATA / f'{c}-{dtype}'
            assert (folder / 'COMPLETE').exists()
            meta = load(folder / 'metadata.json')
            if c == 'b500':
                assert meta['git_commit'] == freeze_commit
            if c != 'b500':
                assert sha((folder / 'scores.jsonl').read_bytes()) == freeze['development'][c][dtype]
            archive = HERE / 'raw-cache' / f'{c}-{dtype}-scores.jsonl.gz'
            assert gzip.decompress(archive.read_bytes()) == (folder / 'scores.jsonl').read_bytes()
    predictions = rows(HERE / 'predictions.jsonl')
    assert len(predictions) == 2500
    evaluation = load(HERE / 'evaluation.json')
    categories = list(load(HERE / 'best_config.json')['categories'])
    for key, expected in evaluation.items():
        corpus, dtype = key.split('-')
        selected = [r for r in predictions if r['corpus'] == corpus and r['dtype'] == dtype]
        assert len(selected) == int(corpus[1:])
        assert len({r['id'] for r in selected}) == len(selected)
        for c in categories:
            actual = metrics([c in r['expected'] for r in selected], [c in r['actual'] for r in selected])
            assert all(actual[k] == expected['per_category'][c][k] for k in actual)
    assert len(list(csv.DictReader((HERE / 'summary.csv').open()))) == 72
    assert len(list(csv.DictReader((HERE / 'errors.csv').open()))) == sum(m['micro']['FP'] + m['micro']['FN'] for m in evaluation.values())
    perf = load(HERE / 'performance.json')
    for dtype in ('fp32', 'fp16'):
        assert len(perf[f'speed-{dtype}']['groups']) == 4
        assert (DATA / f'speed-{dtype}/COMPLETE').exists()
    with gzip.open(HERE / 'development-grid.jsonl.gz', 'rt') as stream:
        assert sum(1 for _ in stream) == 131328
    print('Validated 1250 source EML hashes, 2500 predictions, 72 category rows, 131328 development decisions, both speed experiments and pre-holdout freeze')


if __name__ == '__main__':
    main()