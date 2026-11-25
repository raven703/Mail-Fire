"""Read-only benchmark of original benchmark-350 image attachments, no mail import."""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        row = [i]
        for j, right in enumerate(b, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j-1] + (left != right)))
        previous = row
    return previous[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', choices=['rapidocr', 'paddleocr', 'surya'], required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--container', help='Existing disposable container instead of Compose service')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    service = 'ocr-surya' if args.provider == 'surya' else 'ocr-parser'
    references = {r['sha256']: r for r in json.loads((root/'test-data/results-surya-ocr/inputs.json').read_text())}
    results = []
    hashes = {}
    manifest = [json.loads(line) for line in (root/'test-data/benchmark-350-v1/manifest.jsonl').read_text().splitlines()]
    for item in manifest:
        path = root/'test-data/benchmark-350-v1'/item['file']
        raw = path.read_bytes()
        hashes[item['id']] = hashlib.sha256(raw).hexdigest()
        mail = BytesParser(policy=policy.default).parsebytes(raw)
        for attachment in mail.iter_attachments():
            name = attachment.get_filename() or ''
            if Path(name.lower()).suffix not in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.pdf'}:
                continue
            data = attachment.get_payload(decode=True)
            sha = hashlib.sha256(data).hexdigest()
            request = {'operation': 'extract', 'data': base64.b64encode(data).decode(), 'name': name,
                       'provider': args.provider, 'force_ocr': True}
            code = "import sys,httpx; r=httpx.post('http://localhost:8090/parse',content=sys.stdin.buffer.read(),timeout=205); r.raise_for_status(); print(r.text)"
            started = time.perf_counter()
            row = {'id': item['id'], 'sha256': sha, 'provider': args.provider}
            try:
                command = ['docker', 'exec', '-i', args.container] if args.container else ['docker', 'compose', 'exec', '-T', service]
                response = subprocess.run(command + ['python', '-c', code],
                                          input=json.dumps(request).encode(), capture_output=True, timeout=215, cwd=root)
                if response.returncode:
                    raise RuntimeError('provider request failed')
                result = json.loads(response.stdout)
                row.update(text=result['text'], status=result['status'], details=result['details'])
                ref = references.get(sha)
                if ref:
                    expected = ref['expected']
                    row['reference'] = expected
                    row['cer'] = distance(expected, result['text'])/max(1,len(expected))
                    row['wer'] = distance(expected.split(),result['text'].split())/max(1,len(expected.split()))
                    row['identifier_exact'] = ref['identifier'] in result['text'] if ref.get('identifier') else None
                # Existing detectors, isolated parser. No rule modification or DB writes.
                detection = {'operation': 'detect', 'data': base64.b64encode(result['text'].encode()).decode(), 'name': ''}
                detected = subprocess.run(['docker','compose','exec','-T','parser','python','-c', code],
                                          input=json.dumps(detection).encode(),capture_output=True,timeout=140,cwd=root)
                row['detectors'] = json.loads(detected.stdout) if detected.returncode == 0 else {'error': 'detector request failed'}
            except Exception as exc:
                row['error'] = type(exc).__name__
            row['wall_seconds'] = time.perf_counter()-started
            results.append(row)
            Path(args.output).write_text(json.dumps({'provider': args.provider,'results': results,'input_hashes': hashes},ensure_ascii=False,indent=2))
            print(item['id'],row.get('status',row.get('error')),round(row['wall_seconds'],2),flush=True)
    assert all(hashlib.sha256((root/'test-data/benchmark-350-v1'/item['file']).read_bytes()).hexdigest() == hashes[item['id']] for item in manifest)
    print('Original mail hashes unchanged; benchmark complete',flush=True)


if __name__ == '__main__':
    main()
