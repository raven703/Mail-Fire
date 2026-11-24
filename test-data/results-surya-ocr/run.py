"""CPU-only official Surya 2.5 API; run in the isolated test venv."""
import hashlib
import json
import os
import platform
import threading
import time
import traceback
from importlib.metadata import version
from pathlib import Path

import psutil
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent


def main():
    from surya import RecognitionPredictor, SuryaInferenceManager

    process = psutil.Process()
    samples = []
    stop = threading.Event()

    def monitor():
        while not stop.wait(0.25):
            rss = cpu = 0
            for p in [process, *process.children(recursive=True)]:
                try:
                    rss += p.memory_info().rss
                    t = p.cpu_times()
                    cpu += t.user + t.system
                except psutil.Error:
                    pass
            samples.append({'time': time.monotonic(), 'rss': rss, 'cpu_seconds': cpu})

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    started = time.perf_counter()
    manager = SuryaInferenceManager()
    predictor = RecognitionPredictor(manager)
    setup_seconds = time.perf_counter() - started
    results = []
    for item in json.loads((ROOT / 'inputs.json').read_text()):
        path = ROOT / 'png' / (item['id'] + '.png')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        image = Image.open(path)
        image.load()
        before = len(samples)
        started = time.perf_counter()
        result = dict(item)
        try:
            prediction = predictor([image])[0]
            raw = prediction.model_dump(mode='json')
            result['prediction'] = raw
            result['text'] = '\n'.join(
                BeautifulSoup(b['html'], 'html.parser').get_text(' ', strip=True)
                for b in raw['blocks'] if not b.get('skipped'))
            result['block_errors'] = [b for b in raw['blocks'] if b.get('error')]
            result['error'] = None
        except Exception:
            result['error'] = traceback.format_exc()
            result['text'] = ''
        result['seconds'] = time.perf_counter() - started
        selected = samples[before:]
        result['peak_tree_rss_bytes'] = max((s['rss'] for s in selected), default=None)
        result['cpu_seconds_approx'] = (selected[-1]['cpu_seconds'] - selected[0]['cpu_seconds']
                                        if len(selected) > 1 else None)
        result['cpu_percent_approx'] = (100 * result['cpu_seconds_approx'] / result['seconds']
                                        if result['cpu_seconds_approx'] is not None else None)
        results.append(result)
        (ROOT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(item['id'], result['seconds'], repr(result['text']), flush=True)
    stop.set()
    watcher.join()
    environment = {
        'surya_ocr': version('surya-ocr'), 'python': platform.python_version(),
        'platform': platform.platform(), 'cpu_count': os.cpu_count(),
        'cpu_info': Path('/proc/cpuinfo').read_text(),
        'memory_total': psutil.virtual_memory().total,
        'backend': 'llamacpp CPU; ngl=0; no-mmproj-offload', 'gpu_used': False,
        'vram_bytes': 0, 'settings': {k: v for k, v in os.environ.items()
                                    if k.startswith(('SURYA_', 'LLAMA_', 'CUDA_', 'OMP_'))},
        'model_revision': 'eb78671ae9af9bdddfac2e25507c55337b6098e2',
        'model_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in Path('/tmp/mice-surya-test/models').glob('*.gguf')},
        'setup_seconds': setup_seconds,
        'peak_tree_rss_bytes': max((s['rss'] for s in samples), default=None),
        'resource_method': 'process tree RSS sum / cumulative CPU sampled at 250ms; RSS may double-count shared pages',
        'timing': 'single sequential call per image, model reused; first call may include lazy server startup',
    }
    (ROOT / 'environment.json').write_text(json.dumps(environment, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()