"""Run in an isolated Tesseract container against read-only extracted PNGs."""
import csv
import hashlib
import json
import re
import statistics
import subprocess
import time
from pathlib import Path


def normalize(text):
    # Preserve Unicode confusables and digits: no transliteration/correction.
    return ' '.join(text.split())


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def evaluate(expected, text, identifier):
    a, b = normalize(expected), normalize(text)
    return {'cer': distance(a, b) / len(a), 'edit_distance': distance(a, b),
            'reference_characters': len(a), 'full_exact': a == b,
            'identifier_expected': identifier,
            'identifier_exact': identifier in re.findall(r'\d+', text) if identifier else None}


def main():
    root = Path('/input')
    output = Path('/output')
    inputs = json.loads((root / 'inputs.json').read_text())
    paddle = {r['id']: r for r in json.loads((root / 'paddle-baseline.json').read_text())}
    results = []
    version = subprocess.check_output(['tesseract', '--version'], stderr=subprocess.STDOUT).decode()
    packages = subprocess.check_output(['dpkg-query', '-W', 'tesseract-ocr*']).decode()
    models = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in (Path('/best'), Path('/usr/share/tesseract-ocr/5/tessdata'))
              for p in folder.glob('*.traineddata')}
    for cohort in ('current', 'initial_pr'):
        for item in inputs:
            expected_line = item['expected_line'] if cohort == 'current' else item['initial_pr_expected_line']
            watermark = ('SYNTHETIC OCR TEST' if cohort == 'initial_pr' or
                         item['same_as_initial_pr'] else 'SYNTHETIC OCR FIXTURE')
            expected = expected_line + '\n' + watermark
            identifiers = re.findall(r'\d+', expected_line)
            identifier = identifiers[0] if identifiers else None
            folder = 'png' if cohort == 'current' else 'png-initial-pr'
            path = root / folder / (item['id'] + '.png')
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            assert sha == item['sha256' if cohort == 'current' else 'initial_pr_sha256']
            if cohort == 'current' or item['same_as_initial_pr']:
                text = paddle[item['id']]['text']
                results.append({'cohort': cohort, 'id': item['id'], 'engine': 'paddle_baseline',
                                'model': 'recorded', 'lang': 'ru', 'psm': None,
                                'text': text, 'expected': expected, 'sha256': sha,
                                'seconds_median': None, 'seconds_runs': [],
                                **evaluate(expected, text, identifier)})
            for model, directory in [('debian', '/usr/share/tesseract-ocr/5/tessdata'), ('best', '/best')]:
                for lang in ('eng', 'rus+eng'):
                    for psm in (6, 7, 11):
                        command = ['tesseract', str(path), 'stdout', '--tessdata-dir', directory,
                                   '-l', lang, '--oem', '1', '--psm', str(psm)]
                        times, texts, warnings = [], [], []
                        for _ in range(3):
                            start = time.perf_counter()
                            run = subprocess.run(command, capture_output=True, timeout=60, check=True)
                            times.append(time.perf_counter() - start)
                            texts.append(run.stdout.decode().strip())
                            warnings.append(run.stderr.decode())
                        assert len(set(texts)) == 1
                        results.append({'cohort': cohort, 'id': item['id'], 'engine': 'tesseract',
                                        'model': model, 'lang': lang, 'psm': psm,
                                        'text': texts[0], 'expected': expected, 'sha256': sha,
                                        'seconds_median': statistics.median(times), 'seconds_runs': times,
                                        'stderr': warnings[0], **evaluate(expected, texts[0], identifier)})
            (output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (output / 'environment.json').write_text(json.dumps({'version': version, 'packages': packages,
        'model_sha256': models, 'repeats': 3, 'OMP_THREAD_LIMIT': '1',
        'timing': 'CLI wall clock incl. process startup and model loading; median of 3 runs',
        'cer': 'Levenshtein / reference length; whitespace collapsed; case and Unicode preserved; full visible text including watermark',
        'paddle_timing': 'Unavailable in saved baseline; not fabricated or inferred.',
        'best_commit': 'e12c65a915945e4c28e237a9b52bc4a8f39a0cec'}, indent=2))
    keys = list(dict.fromkeys(k for r in results for k in r))
    with (output / 'results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in r.items()}
                         for r in results)


if __name__ == '__main__':
    main()