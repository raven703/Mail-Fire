"""CUDA-only cached NLI. Does not load labels or detector results."""
import argparse
import json
import os
import platform
import resource
import subprocess
import time

from common import DATA, HERE, REVISION, load, rows, save, sha, windows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=['b350', 'b400', 'b500', 'speed'])
    parser.add_argument('--dtype', choices=['fp32', 'fp16'], required=True)
    parser.add_argument('--batch-size', type=int, default=16)
    args = parser.parse_args()
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    assert torch.cuda.is_available() and '4060' in torch.cuda.get_device_name(0)
    torch.set_num_threads(2)
    torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    spec = load(HERE / 'hypotheses.json')
    order = [(c, h['id'], h['text']) for c, v in spec['categories'].items() for h in v['hypotheses']]
    if args.corpus == 'b500':
        freeze = load(HERE / 'freeze.json')
        assert freeze['best_config_sha256'] == sha((HERE / 'best_config.json').read_bytes())
        assert freeze['hypotheses_sha256'] == sha((HERE / 'hypotheses.json').read_bytes())
        subprocess.run(['git', '-C', str(HERE), 'diff', '--exit-code', 'HEAD', '--',
                        str(HERE / 'best_config.json'), str(HERE / 'hypotheses.json'), str(HERE / 'freeze.json')], check=True)
        committed = subprocess.check_output(['git', '-C', str(HERE), 'show', 'HEAD:test-data/horizon-benchmark/freeze.json'])
        assert sha(committed) == sha((HERE / 'freeze.json').read_bytes())
        needed = { (c, h) for c, cfg in load(HERE / 'best_config.json')['categories'].items() for h in cfg['hypotheses'] }
        order = [o for o in order if o[:2] in needed]
    folder = DATA / f'{args.corpus}-{args.dtype}'
    folder.mkdir(exist_ok=False)
    model_path = '/home/user/hf-model-benchmark-data/models/horizon'
    weights_hash = sha(open(model_path + '/model.safetensors', 'rb').read())
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True,
                trust_remote_code=False, dtype=torch.float32 if args.dtype == 'fp32' else torch.float16,
                attn_implementation='eager').to('cuda:0').eval()
    assert model.config.id2label == {0: 'not_entailment', 1: 'entailment'}
    source = 'b350' if args.corpus == 'speed' else args.corpus
    texts = rows(DATA / f'{source}-texts.jsonl')
    assert sha((DATA / f'{source}-texts.jsonl').read_bytes()) == load(HERE / f'{source}-provenance.json')['texts_sha256']

    def score(premises, hypotheses):
        encoded = tokenizer(premises, hypotheses, padding=True, truncation='only_first', max_length=512, return_tensors='pt')
        encoded = {k: v.to('cuda:0') for k, v in encoded.items()}
        with torch.inference_mode():
            logits = model(**encoded).logits.float()
            values = logits.softmax(-1)[:, 1]
        assert torch.isfinite(values).all()
        return values.cpu().numpy()

    score(['Разговор о рабочем письме.'] * 4, [o[2] for o in order[:4]])
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    save(folder / 'metadata.json', dict(revision=REVISION, weights_sha256=weights_hash,
        hypotheses_sha256=sha((HERE / 'hypotheses.json').read_bytes()), order=order,
        dtype=args.dtype, gpu=torch.cuda.get_device_name(0), torch=torch.__version__,
        python=platform.python_version(), batch_size=args.batch_size, max_tokens=512,
        window_characters=900, overlap=100, score='softmax([not_entailment, entailment])[1]',
        text_sha256=sha((DATA / f'{source}-texts.jsonl').read_bytes()),
        git_commit=subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', 'HEAD'], text=True).strip()))
    timings = []
    if args.corpus == 'speed':
        # Same fixed first 12 development emails, three passes after warm-up.
        for count in (12, 24, 48, 96):
            chosen = [o for i, o in enumerate(order) if i % 8 < count // 12]
            for repeat in range(3):
                for row in texts[:12]:
                    start = time.perf_counter()
                    pairs = [(w, h[2]) for w in windows(row['text']) for h in chosen]
                    for pos in range(0, len(pairs), args.batch_size):
                        batch = pairs[pos:pos + args.batch_size]
                        score([p[0] for p in batch], [p[1] for p in batch])
                    torch.cuda.synchronize()
                    timings.append(dict(id=row['id'], hypotheses=count, repeat=repeat,
                                        seconds=time.perf_counter() - start, pairs=len(pairs)))
    else:
        with (folder / 'scores.jsonl').open('x', encoding='utf-8') as output:
            for i, row in enumerate(texts):
                start = time.perf_counter()
                chunks = list(windows(row['text']))
                pairs = [(w, h[2]) for w in chunks for h in order]
                values = []
                for pos in range(0, len(pairs), args.batch_size):
                    batch = pairs[pos:pos + args.batch_size]
                    values.extend(score([p[0] for p in batch], [p[1] for p in batch]).tolist())
                torch.cuda.synchronize()
                elapsed = time.perf_counter() - start
                matrix = np.asarray(values).reshape(len(chunks), len(order)).tolist()
                output.write(json.dumps(dict(id=row['id'], text_sha256=row['text_sha256'],
                    characters=len(row['text']), scores=matrix, seconds=elapsed)) + '\n')
                output.flush()
                timings.append(dict(id=row['id'], seconds=elapsed, windows=len(chunks), pairs=len(pairs)))
                if (i + 1) % 10 == 0:
                    print(args.corpus, args.dtype, i + 1, '/', len(texts), flush=True)
    save(folder / 'performance.json', dict(timings=timings,
        seconds=sum(t['seconds'] for t in timings),
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        peak_vram_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_vram_reserved_bytes=torch.cuda.max_memory_reserved(),
        scope='Warmed CUDA inference incl tokenization, transfers, per-window scores; excludes model load, extraction and disk writes'))
    assert weights_hash == sha(open(model_path + '/model.safetensors', 'rb').read())
    (folder / 'COMPLETE').write_text('complete\n')


if __name__ == '__main__':
    main()