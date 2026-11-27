"""Actual offline CPU smoke, NOT a corpus quality benchmark or calibration."""

import json
import os
import platform
import resource
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["MICE_HORIZON_DEVICE"] = "cpu"

from app.horizon import analyze_document, score_pairs  # noqa: E402


def main():
    import torch
    import transformers

    defaults = json.loads((ROOT / "app/horizon_defaults.json").read_text())
    rules = [SimpleNamespace(id=cid, config=cfg) for cid, cfg in defaults.items()]
    t = time.perf_counter()
    probe, weights = score_pairs([("Завтра взорву офис компании.", "Письмо содержит угрозу взрыва.")])
    cold = time.perf_counter() - t
    examples = [
        ("short", "Завтра взорву офис компании."),
        ("safe", "Спасибо за встречу. Хорошего дня!"),
        ("long", "Обсуждаем общедоступные новости. " * 55 + "Завтра взорву офис компании."),
    ]
    rows = []
    for name, text in examples:
        started = time.perf_counter()
        predictions, errors = analyze_document(text, rules)
        assert not errors and len(predictions) == 12
        rows.append(
            dict(
                name=name,
                characters=len(text),
                seconds=time.perf_counter() - started,
                predictions=predictions,
                errors=errors,
            )
        )
    result = dict(
        python=platform.python_version(),
        platform=platform.platform(),
        torch=torch.__version__,
        transformers=transformers.__version__,
        device="cpu",
        CUDA_VISIBLE_DEVICES="",
        weights_sha256=weights,
        cold_probe_seconds=cold,
        cold_probe_score=probe,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        examples=rows,
        warning="Synthetic smoke only. Long-window aggregation not calibrated on natural long messages.",
    )
    (Path(__file__).parent / "cpu-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print("CPU smoke complete:", [(r["name"], round(r["seconds"], 3)) for r in rows])


if __name__ == "__main__":
    main()
