"""Isolated frozen-weight GPU inference; each model runs in a separate process."""
import argparse
import gc
import json
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
from importlib.metadata import version
from pathlib import Path

from prepare import CORPUS, HERE, digest, windows, write_json

DATA = Path.home() / "hf-model-benchmark-data"
RESULTS = HERE / "results"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def verify_frozen():
    frozen = json.loads((RESULTS / "cohorts.json").read_text())
    assert digest((CORPUS / "manifest.jsonl").read_bytes()) == frozen["manifest_sha256"]
    assert digest((RESULTS / "prepared.jsonl").read_bytes()) == frozen["prepared_sha256"]
    assert digest((HERE / "protocol.json").read_bytes()) == frozen["protocol_sha256"]
    for name, expected in frozen["source_sha256"].items():
        assert digest((CORPUS / name).read_bytes()) == expected, name
    return frozen


def model_load(key, info):
    import torch
    from huggingface_hub import snapshot_download
    from transformers import (
        AutoConfig,
        AutoModel,
        AutoModelForSequenceClassification,
        AutoModelForTokenClassification,
        AutoTokenizer,
        BertConfig,
    )

    folder = DATA / "models" / key
    patterns = ["*.json", "*.safetensors", "spm.model", "*.txt"]
    if key == "gloomreach":
        patterns.append("pytorch_model.bin")
    snapshot_download(info["repo"], revision=info["revision"], local_dir=folder,
                      allow_patterns=patterns, ignore_patterns=["onnx/*", "training_args.bin"])
    tokenizer = AutoTokenizer.from_pretrained(folder, trust_remote_code=False)
    if key == "gloomreach":
        class MultiTaskToxicityEncoder(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.encoder = AutoModel.from_config(BertConfig.from_dict(info["base_architecture"]["config"]))
                hidden = self.encoder.config.hidden_size
                self.profanity_head = torch.nn.Linear(hidden, 1)
                self.threat_head = torch.nn.Linear(hidden, 1)
                self.illegal_head = torch.nn.Linear(hidden, 1)

            def forward(self, input_ids, attention_mask, **kwargs):
                cls = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0, :]
                return torch.cat([self.profanity_head(cls), self.threat_head(cls), self.illegal_head(cls)], dim=1)

        model = MultiTaskToxicityEncoder()
        state = torch.load(folder / "pytorch_model.bin", map_location="cpu", weights_only=True)
        if "model_state_dict" in state:
            state = state["model_state_dict"]
        # No missing/unexpected keys are allowed; no substitute encoder weights.
        model.load_state_dict(state, strict=True)
        del state
        labels = {0: "profanity", 1: "threat", 2: "illegal"}
    else:
        config = AutoConfig.from_pretrained(folder, trust_remote_code=False)
        cls = AutoModelForTokenClassification if key == "redmadrobot" else AutoModelForSequenceClassification
        kwargs = {"attn_implementation": "eager"} if key == "horizon" else {}
        model = cls.from_pretrained(folder, config=config, trust_remote_code=False, dtype=torch.float32, **kwargs)
        labels = {int(k): v for k, v in config.id2label.items()}
    return model.to("cuda:0").eval(), tokenizer, labels


def classify(key, model, tokenizer, labels, text, protocol):
    import torch

    chunks = list(windows(text, protocol["chunk_characters"], protocol["chunk_overlap_characters"]))
    tasks, truncated = [], 0
    if key in {"horizon", "mdeberta"}:
        for offset, chunk in chunks:
            for category, definition in protocol["categories"].items():
                tasks.append((offset, chunk, category, protocol["hypothesis_template"].format(definition["description"])))
        inverse = {label.lower(): i for i, label in labels.items()}
        entail = inverse["entailment"]
        negative = inverse.get("contradiction", inverse.get("not_entailment"))
        assert negative is not None
    else:
        tasks = [(offset, chunk, None, None) for offset, chunk in chunks]
    output = []
    for start in range(0, len(tasks), protocol["batch_size"]):
        batch = tasks[start:start + protocol["batch_size"]]
        premises = [row[1] for row in batch]
        kwargs = dict(padding=True, truncation="only_first", max_length=protocol["max_tokens"], return_tensors="pt")
        if key in {"horizon", "mdeberta"}:
            hypotheses = [row[3] for row in batch]
            raw_lengths = [len(tokenizer(a, b)["input_ids"]) for a, b in zip(premises, hypotheses)]
            encoded = tokenizer(premises, hypotheses, **kwargs)
        else:
            raw_lengths = [len(tokenizer(a)["input_ids"]) for a in premises]
            encoded = tokenizer(premises, **kwargs)
        truncated += sum(length > protocol["max_tokens"] for length in raw_lengths)
        encoded = {k: v.to("cuda:0") for k, v in encoded.items()}
        with torch.inference_mode():
            value = model(**encoded)
            logits = value if key == "gloomreach" else value.logits
            if key == "gloomreach":
                probabilities = logits.sigmoid()
            else:
                probabilities = logits.softmax(-1)
            raw_logits = logits.float().cpu().tolist()
            raw_probs = probabilities.float().cpu().tolist()
            nli = logits[:, [negative, entail]].softmax(-1)[:, 1].cpu().tolist() if key in {"horizon", "mdeberta"} else None
        for i, (offset, chunk, category, _) in enumerate(batch):
            output.append(dict(start=offset, end=offset + len(chunk), category=category,
                               logits=raw_logits[i], probabilities={labels[j]: p for j, p in enumerate(raw_probs[i])},
                               score=nli[i] if nli is not None else None))
    if key in {"horizon", "mdeberta"}:
        scores = {c: max(r["score"] for r in output if r["category"] == c) for c in protocol["categories"]}
    elif key == "gloomreach":
        scores = {"threat": max(r["probabilities"]["threat"] for r in output)}
    else:
        assert labels == {0: "Phishing", 1: "Legit"}, labels
        scores = {"phishing": max(r["probabilities"]["Phishing"] for r in output)}
    return dict(scores=scores, windows=output, truncated_windows=truncated)


def ner(model, tokenizer, labels, text, protocol):
    import torch

    entities, token_rows, truncated = {}, [], 0
    for base, chunk in windows(text, protocol["chunk_characters"], protocol["chunk_overlap_characters"]):
        full = tokenizer(chunk)
        truncated += int(len(full["input_ids"]) > protocol["max_tokens"])
        encoded = tokenizer(chunk, return_offsets_mapping=True, return_tensors="pt", truncation=True,
                            max_length=protocol["max_tokens"])
        offsets = encoded.pop("offset_mapping")[0].tolist()
        with torch.inference_mode():
            probabilities = model(**{k: v.to("cuda:0") for k, v in encoded.items()}).logits.softmax(-1)[0].cpu()
        current = None

        def flush():
            if current:
                key = (current["label"], current["start"], current["end"])
                current["text"] = text[current["start"]:current["end"]]
                entities[key] = dict(current)

        for (start, end), probs in zip(offsets, probabilities):
            if end <= start:
                continue
            index = int(probs.argmax())
            label, score = labels[index], float(probs[index])
            token_rows.append(dict(start=base + start, end=base + end, label=label, score=score))
            if label == "O":
                flush()
                current = None
                continue
            prefix, kind = label.split("-", 1)
            if prefix == "I" and current and current["label"] == kind:
                current["end"] = base + end
                current["score"] = min(current["score"], score)
            else:
                flush()
                current = dict(label=kind, start=base + start, end=base + end, score=score)
        flush()
    return dict(entities=list(entities.values()), tokens=token_rows, truncated_windows=truncated)


def worker(key):
    import psutil
    import torch

    assert torch.cuda.is_available(), "GPU unavailable: CPU fallback is forbidden"
    protocol = json.loads((HERE / "protocol.json").read_text())
    verify_frozen()
    info = json.loads((RESULTS / "model_audit.json").read_text())[key]
    if info["status"] in {"blocked_gpu", "unavailable"}:
        write_json(RESULTS / f"{key}-status.json", dict(status=info["status"], reason=info["reason"],
                   smoke="not executable on requested GPU without changing artifact"))
        return
    process, peak, stop = psutil.Process(), [0], threading.Event()

    def sample():
        while not stop.wait(.02):
            peak[0] = max(peak[0], process.memory_info().rss)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    torch.cuda.reset_peak_memory_stats()
    begin = time.perf_counter()
    try:
        model, tokenizer, labels = model_load(key, info)
        assert next(model.parameters()).device.type == "cuda"
        loaded = time.perf_counter()
        prepared = read_jsonl(RESULTS / "prepared.jsonl")
        # Add task-specific positives without removing fixed hard-negative controls.
        probes = ["Пожалуйста, пришлите пароль и код из СМС для входа по ссылке http://login.example.org.",
                  "Я взорву ваш офис завтра.", "Анна Смирнова живёт в Казани. Контакт test@example.org.",
                  "Это учебный пример фишинга. Никому не сообщайте пароль.", "Угрозы не поступали, обсуждаем только учения."]
        def predict(text):
            if key == "redmadrobot":
                return ner(model, tokenizer, labels, text, protocol)
            return classify(key, model, tokenizer, labels, text, protocol)
        smoke_rows = [dict(id=f"probe-{i}", text=text, **predict(text)) for i, text in enumerate(probes)]
        write_json(RESULTS / f"{key}-smoke.json", dict(labels=labels, device=str(next(model.parameters()).device),
                    dtype=str(next(model.parameters()).dtype), examples=smoke_rows,
                    interpretation="NLI independent entailment vs contradiction/not_entailment softmax; phishing class 0; threat sigmoid head; NER BIO argmax"))
        torch.cuda.synchronize()
        main_start = time.perf_counter()
        with (RESULTS / f"{key}-predictions.jsonl").open("x", encoding="utf-8") as output:
            for i, row in enumerate(prepared):
                result = predict(row["text"])
                record = dict(model=key, repo=info["repo"], revision=info["revision"], id=row["id"],
                              text_sha256=row["text_sha256"], extraction_errors=row["extraction_errors"],
                              provenance=[{k: v for k, v in s.items() if k != "text"} for s in row["segments"]], **result)
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
                if (i + 1) % 25 == 0:
                    print(key, i + 1, flush=True)
        if key == "redmadrobot":
            fixture = json.loads((HERE / "ner_fixture.json").read_text())
            write_json(RESULTS / "ner-fixture-predictions.json", [dict(id=r["id"], **predict(r["text"])) for r in fixture["examples"]])
        torch.cuda.synchronize()
        end = time.perf_counter()
        write_json(RESULTS / f"{key}-performance.json", dict(device="cuda:0", dtype="float32", messages=len(prepared),
                   model_load_download_seconds=loaded - begin, main_seconds=end - main_start,
                   messages_per_second=len(prepared) / (end - main_start), peak_process_rss_bytes=peak[0],
                   peak_vram_allocated_bytes=torch.cuda.max_memory_allocated(), peak_vram_reserved_bytes=torch.cuda.max_memory_reserved(),
                   measurement="RSS sampled every 20ms; VRAM is process PyTorch allocated/reserved, not total desktop usage; main includes JSON serialization and NER fixture"))
        write_json(RESULTS / f"{key}-status.json", dict(status="completed", labels=labels))
        model = None
    except Exception:
        traceback.print_exc()
        write_json(RESULTS / f"{key}-status.json", dict(status="failed", error=traceback.format_exc()))
        raise
    finally:
        stop.set()
        thread.join()
        gc.collect()
        torch.cuda.empty_cache()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    import torch

    assert torch.cuda.is_available(), "GPU unavailable: benchmark aborted"
    verify_frozen()
    envfile = RESULTS / "environment.json"
    if envfile.exists():
        raise FileExistsError("Refusing to overwrite an existing run")
    audit = json.loads((RESULTS / "model_audit.json").read_text())
    x = torch.ones((512, 512), device="cuda:0")
    environment = dict(python=sys.version, platform=platform.platform(), cuda_build=torch.version.cuda,
        gpu=torch.cuda.get_device_name(), vram_bytes=torch.cuda.get_device_properties(0).total_memory,
        cuda_matmul=float((x @ x)[0, 0]), driver=subprocess.check_output(["nvidia-smi"], text=True),
        packages={p: version(p) for p in ("torch", "transformers", "huggingface-hub", "psutil", "pypdf", "beautifulsoup4")},
        models=audit, protocol=json.loads((HERE / "protocol.json").read_text()),
        git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip(),
        run_started_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        fixture_sha256=digest((HERE / "ner_fixture.json").read_bytes()))
    write_json(envfile, environment)
    del x
    torch.cuda.empty_cache()
    logs = DATA / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for key in audit:
        print("START", key, flush=True)
        with (logs / f"{key}.log").open("w") as stream:
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", key],
                            stdout=stream, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUNBUFFERED="1"))
        print("END", key, completed.returncode, flush=True)


if __name__ == "__main__":
    main()