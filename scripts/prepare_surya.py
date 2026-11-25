"""Fetch the pinned OCR-only model files; validate every byte against the lock."""
import hashlib
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
models = root / 'surya/models'
lock = json.loads((root / 'surya/models.lock.json').read_text())
revisions = {'detector': 'text_detection/2025_05_07', 'recognizer': 'text_recognition/2025_05_16'}
for name, expected in lock.items():
    target = models / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        provider, filename = name.split('/', 1)
        temporary = target.with_suffix(target.suffix + '.part')
        urllib.request.urlretrieve('https://models.datalab.to/' + revisions[provider] + '/' + filename, temporary)
        temporary.replace(target)
    with target.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError('Surya checksum mismatch: ' + name)
print('Surya model checksums verified')
