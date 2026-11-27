"""Standalone benchmark utilities. No production application imports."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = Path('/home/user/hf-model-benchmark-data/horizon-category')
INPUTS = DATA / 'inputs'
REVISION = 'a9a5a24e58c794a0f7532d3de842236435a9ae22'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def windows(text, size=900, overlap=100):
    if size <= overlap or overlap < 0:
        raise ValueError('Invalid window settings')
    start = 0
    while True:
        end = min(start + size, len(text))
        yield text[start:end]
        if end == len(text):
            break
        start = end - overlap


def metrics(y, pred):
    tp = sum(a and b for a, b in zip(y, pred))
    fp = sum(not a and b for a, b in zip(y, pred))
    fn = sum(a and not b for a, b in zip(y, pred))
    tn = len(y) - tp - fp - fn
    return dict(TP=int(tp), FP=int(fp), FN=int(fn), TN=int(tn),
                precision=tp / (tp + fp) if tp + fp else 0.,
                recall=tp / (tp + fn) if tp + fn else 0.,
                F1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
                FPR=fp / (fp + tn) if fp + tn else 0.)


def average_precision(y, scores):
    """Non-interpolated PR-AUC/AP, tie-aware (not trapezoidal area)."""
    positives = sum(y)
    if not positives:
        return 0.
    groups = {}
    for label, score in zip(y, scores):
        groups.setdefault(float(score), []).append(label)
    tp = seen = 0
    area = 0.
    for score in sorted(groups, reverse=True):
        group = groups[score]
        gained = sum(group)
        tp += gained
        seen += len(group)
        area += gained / positives * tp / seen
    return area