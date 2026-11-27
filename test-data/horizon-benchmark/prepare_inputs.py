"""Reuse verified frozen extraction, selecting only text; keep labels separately."""
import argparse

from common import DATA, HERE, INPUTS, ROOT, rows, save, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=['b350', 'b400', 'b500'])
    args = parser.parse_args()
    c = args.corpus
    if c == 'b350':
        corpus = ROOT / 'test-data/benchmark-350-v1'
        observations = ROOT / 'test-data/results-benchmark350-20261123/observations.jsonl'
    elif c == 'b400':
        corpus = INPUTS / 'b400/test-data/benchmark-400-v1'
        observations = INPUTS / 'b400-observations.jsonl'
    else:
        if not (HERE / 'freeze.json').exists():
            raise RuntimeError('B500 preparation requires the committed selection freeze')
        corpus = INPUTS / 'b500/test-data/benchmark-500-v1'
        observations = INPUTS / 'baseline/test-data/results-benchmark500-v1/observations.jsonl'
    manifest = rows(corpus / 'manifest.jsonl')
    obs = {r['id']: r for r in rows(observations)}
    assert len(obs) == len(manifest) == int(c[1:])
    inputs, labels, hashes = [], [], {}
    for row in manifest:
        item = obs[row['id']]
        file = (corpus / row['file']).resolve()
        assert file.is_relative_to(corpus.resolve())
        digest = sha(file.read_bytes())
        assert digest == item['sha256'], row['id']
        text = item['text']
        assert isinstance(text, str) and text.strip()
        # No analysis, ground truth, attachment hints, or normalization outputs.
        inputs.append(dict(id=row['id'], text=text, text_sha256=sha(text.encode())))
        labels.append(dict(id=row['id'], expected=row['expected_semantic_categories'],
                           group=row['group'], scenario=row.get('scenario'),
                           extraction_status=item.get('status'),
                           attachment_statuses=[a.get('status') for a in item.get('attachments', [])]))
        hashes[row['file']] = digest
    DATA.mkdir(parents=True, exist_ok=True)
    for name, values in [('texts', inputs), ('labels', labels)]:
        with (DATA / f'{c}-{name}.jsonl').open('x', encoding='utf-8') as stream:
            for value in values:
                import json
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    save(HERE / f'{c}-provenance.json', dict(messages=len(inputs),
         manifest_sha256=sha((corpus / 'manifest.jsonl').read_bytes()),
         observations_sha256=sha(observations.read_bytes()), source_eml_sha256=hashes,
         texts_sha256=sha((DATA / f'{c}-texts.jsonl').read_bytes()),
         labels_sha256=sha((DATA / f'{c}-labels.jsonl').read_bytes()),
         extraction='Frozen observation text including recorded attachment extraction/OCR; no re-extraction or gold hints',
         statuses={s: sum(r['extraction_status'] == s for r in labels) for s in {r['extraction_status'] for r in labels}}))
    print(c, 'verified', len(inputs), flush=True)


if __name__ == '__main__':
    main()