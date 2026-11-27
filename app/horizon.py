"""Bounded offline NLI; optional imports stay out of web/parser processes."""

import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

MODEL = "Horizon-Labs/multilingual-zeroshot-base"
REVISION = "a9a5a24e58c794a0f7532d3de842236435a9ae22"
MAX_HYPOTHESES = 10
MAX_DOCUMENT_CHARS = 40000
MAX_WINDOWS = 50
MAX_PAIRS = 6000


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("Horizon: ожидается объект настроек")
    out = {}
    for key in ("positive_hypotheses", "excluding_hypotheses"):
        items = config.get(key, [])
        if not isinstance(items, list) or any(
            not isinstance(x, str) or not 3 <= len(x.strip()) <= 600 for x in items
        ):
            raise ValueError("Horizon: гипотеза — 3–600 символов")
        out[key] = list(dict.fromkeys(x.strip() for x in items))
    if (
        not out["positive_hypotheses"]
        or sum(len(config.get(k, [])) for k in ("positive_hypotheses", "excluding_hypotheses"))
        > MAX_HYPOTHESES
    ):
        raise ValueError("Horizon: 1–10 гипотез, минимум одна положительная")
    mode = config.get("combine", "mean")
    if mode not in {"single", "mean", "max", "min", "subtract", "product"}:
        raise ValueError("Horizon: неизвестное объединение")
    p, e = len(out["positive_hypotheses"]), len(out["excluding_hypotheses"])
    if mode in {"subtract", "product"} and (p != 1 or e != 1):
        raise ValueError("Horizon: subtract/product требуют одну положительную и одну исключающую гипотезу")
    if mode not in {"subtract", "product"} and e:
        raise ValueError("Horizon: исключения допустимы только для subtract/product")
    if mode == "single" and p != 1:
        raise ValueError("Horizon single: ровно одна гипотеза")
    aggregation = config.get("aggregation", "max")
    if aggregation not in {"max", "mean", "top2_mean", "noisy_or"}:
        raise ValueError("Horizon: неизвестная агрегация")
    threshold = config.get("threshold", 0.5)
    if type(threshold) not in {int, float} or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Horizon: порог >0 и <=1")
    return {**out, "combine": mode, "aggregation": aggregation, "threshold": threshold}


def fingerprint(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def chunks(text):
    for start in range(0, len(text), 800):
        yield start, text[start : start + 900]
        if start + 900 >= len(text):
            break


def combine(values, mode):
    if mode == "single":
        return values[0]
    if mode == "mean":
        return sum(values) / len(values)
    if mode == "max":
        return max(values)
    if mode == "min":
        return min(values)
    if mode == "subtract":
        return max(0.0, values[0] - values[1])
    if mode == "product":
        return values[0] * (1 - values[1])
    raise ValueError(mode)


def aggregate(values, mode):
    if mode == "max":
        return max(values)
    if mode == "mean":
        return sum(values) / len(values)
    if mode == "top2_mean":
        top = sorted(values)[-2:]
        return sum(top) / len(top)
    if mode == "noisy_or":
        return 1 - math.prod(1 - v for v in values)
    raise ValueError(mode)


def model_directory():
    path = Path(os.environ.get("MICE_HORIZON_MODEL_PATH", "/opt/horizon")).resolve()
    if (
        not path.is_dir()
        or not (path / "config.json").is_file()
        or not (path / "model.safetensors").is_file()
    ):
        raise FileNotFoundError("Horizon local model unavailable")
    return path


@lru_cache(maxsize=1)
def encoder(path, device):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if device not in {"cpu", "cuda"}:
        raise ValueError("Horizon device must be cpu or cuda")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA unavailable; select CPU explicitly")
    torch.set_num_threads(max(1, min(4, int(os.environ.get("MICE_HORIZON_THREADS", "2")))))
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = (
        AutoModelForSequenceClassification.from_pretrained(
            path,
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.float32,
            attn_implementation="eager",
        )
        .to(device)
        .eval()
    )
    if model.config.id2label != {0: "not_entailment", 1: "entailment"}:
        raise ValueError("Horizon requires binary entailment label format")
    # Content identity, not a claim that any admin-supplied local weights equal upstream.
    digest = hashlib.sha256()
    with (Path(path) / "model.safetensors").open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return tokenizer, model, digest.hexdigest()


def score_pairs(pairs):
    import torch

    device = os.environ.get("MICE_HORIZON_DEVICE", "cpu")
    tokenizer, model, weight_hash = encoder(str(model_directory()), device)
    output = []
    for offset in range(0, len(pairs), 8):
        batch = pairs[offset : offset + 8]
        encoded = tokenizer(
            [p[0] for p in batch],
            [p[1] for p in batch],
            padding=True,
            truncation="only_first",
            max_length=512,
            return_tensors="pt",
        )
        with torch.inference_mode():
            scores = model(**{k: v.to(device) for k, v in encoded.items()}).logits.float().softmax(-1)[:, 1]
        if not torch.isfinite(scores).all():
            raise ValueError("Nonfinite Horizon scores")
        output.extend(scores.cpu().tolist())
    return output, weight_hash


def analyze_document(text, rules, *, scorer=score_pairs, budget=None):
    """Return rule-ID keyed predictions plus explicit partial checks. No labels."""
    budget = budget if budget is not None else {"pairs": MAX_PAIRS, "windows": MAX_WINDOWS}
    errors, predictions = [], {}
    if not text.strip():
        return {}, []
    if len(text) > MAX_DOCUMENT_CHARS:
        errors.append({"engine": "horizon", "error": "document_character_limit"})
        text = text[:MAX_DOCUMENT_CHARS]
    fragments = list(chunks(text))
    count = min(len(fragments), budget["windows"])
    if count < len(fragments):
        errors.append({"engine": "horizon", "error": "message_window_limit"})
    fragments = fragments[:count]
    budget["windows"] -= count
    cache = {}  # Request-local only: no unbounded retention of email text.
    for rule in rules:
        try:
            config = validate(rule.config)
            hypotheses = config["positive_hypotheses"] + config["excluding_hypotheses"]
            if not fragments:
                raise ValueError("No remaining Horizon windows")
            pairs = [(fragment, h) for _, fragment in fragments for h in hypotheses]
            missing = list(dict.fromkeys(p for p in pairs if p not in cache))
            if len(missing) > budget["pairs"]:
                errors.append({"engine": "horizon", "rule_id": rule.id, "error": "message_pair_limit"})
                continue
            scores, weight_hash = scorer(missing) if missing else ([], next(iter(cache.values()))[1])
            if len(scores) != len(missing) or any(not math.isfinite(v) or not 0 <= v <= 1 for v in scores):
                raise ValueError("Invalid Horizon score array")
            budget["pairs"] -= len(missing)
            cache.update({p: (score, weight_hash) for p, score in zip(missing, scores)})
            window_scores = [
                combine([cache[(fragment, h)][0] for h in hypotheses], config["combine"])
                for _, fragment in fragments
            ]
            score = aggregate(window_scores, config["aggregation"])
            best = max(range(len(fragments)), key=lambda i: window_scores[i])
            start, fragment = fragments[best]
            predictions[rule.id] = dict(
                confidence=score,
                matched=score >= config["threshold"],
                horizon_score=score,
                horizon_threshold=config["threshold"],
                horizon_hypotheses=[
                    {
                        "text": h,
                        "score": cache[(fragment, h)][0],
                        "polarity": "positive" if i < len(config["positive_hypotheses"]) else "exclude",
                    }
                    for i, h in enumerate(hypotheses)
                ],
                horizon_config_version=fingerprint(config),
                model_version=MODEL,
                model_weights_sha256=weight_hash,
                start=start,
                end=start + len(fragment),
                excerpt=fragment,
                horizon_windows=len(fragments),
                horizon_combine=config["combine"],
                horizon_aggregation=config["aggregation"],
            )
        except Exception as exc:
            errors.append({"engine": "horizon", "rule_id": rule.id, "error": type(exc).__name__})
    return predictions, errors
