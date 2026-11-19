"""Optional fully local SetFit and RuBERT binary classifiers.

Models must be pre-staged as LOCAL directories on the training host.
No LLM, Hugging Face Hub calls, arbitrary uploaded checkpoints, or remote code.
TF-IDF remains the default engine in app.ml.
"""
import hashlib
import io
import os
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import train_test_split

SUPPORTED = {"tfidf", "setfit", "rubert"}
MAX_ARTIFACT = 600 * 1024 * 1024


def _offline():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["WANDB_DISABLED"] = "true"


def _base_path(engine):
    from app.config import settings

    value = settings().ml_setfit_base_path if engine == "setfit" else settings().ml_rubert_base_path
    path = Path(value).resolve()
    if not value or not path.is_dir():
        raise RuntimeError(f"Локальная базовая модель для {engine} отсутствует: {value or '(не задана)'}")
    return str(path)


def _binary_data(examples, category_id):
    from app.ml import group_hash

    groups = {}
    for item in examples:
        h = group_hash(item["text"])
        label = int(category_id in item["labels"])
        if h in groups and groups[h][1] != label:
            raise ValueError("Противоречивые метки для одинакового текста")
        groups[h] = (item["text"], label)
    data = list(groups.values())
    if len(data) < 30:
        raise ValueError("Для обучения нужны минимум 30 разных подтверждённых текстов")
    x = [v[0] for v in data]
    y = np.array([v[1] for v in data])
    if min(np.bincount(y, minlength=2)) < 6:
        raise ValueError("Нужно минимум 6 положительных и 6 отрицательных примеров")
    x_train, x_hold, y_train, y_hold = train_test_split(
        x, y, test_size=.4, random_state=42, stratify=y
    )
    x_val, x_test, y_val, y_test = train_test_split(
        x_hold, y_hold, test_size=.5, random_state=42, stratify=y_hold
    )
    splits = {"train":(x_train,y_train),"validation":(x_val,y_val),"test":(x_test,y_test)}
    for name, (_, labels) in splits.items():
        if len(set(labels)) != 2:
            raise ValueError(f"Недостаточная представленность классов в {name}")
    return splits


def _bundle(folder, engine, category):
    import json

    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        z.writestr("manifest.json", json.dumps({"engine":engine, "category":category, "format":1}))
        for item in Path(folder).rglob("*"):
            if item.is_file():
                z.write(item, arcname="model/" + item.relative_to(folder).as_posix())
    if result.tell() > MAX_ARTIFACT:
        raise ValueError("Обученная модель превышает лимит 600 МиБ")
    return result.getvalue()


def _scores(engine, model, texts, tokenizer=None):
    if engine == "setfit":
        probabilities = np.asarray(model.predict_proba(texts), dtype=float)
        if probabilities.ndim == 1:
            return probabilities
        return probabilities[:, 1]
    import torch

    model.eval()
    output = []
    for start in range(0, len(texts), 8):
        tokens = tokenizer(texts[start:start+8], return_tensors="pt",
                           truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            logits = model(**tokens).logits
        output.extend(torch.softmax(logits, dim=-1)[:, 1].cpu().numpy().tolist())
    return np.array(output)


def train_binary(examples, engine, category, min_f1):
    if engine not in {"setfit", "rubert"}:
        raise ValueError("Неизвестный нейросетевой движок")
    _offline()
    splits = _binary_data(examples, category)
    x_train, y_train = splits["train"]
    with tempfile.TemporaryDirectory(prefix="mailfire-train-") as tmp:
        output = Path(tmp) / "trained"
        if engine == "setfit":
            try:
                from datasets import Dataset
                from setfit import SetFitModel, Trainer, TrainingArguments
            except ImportError as exc:
                raise RuntimeError("Установите опциональные зависимости ml-neural") from exc
            model = SetFitModel.from_pretrained(_base_path(engine), labels=["negative", "positive"])
            data = Dataset.from_dict({"text":x_train, "label":list(map(int,y_train))})
            args = TrainingArguments(
                batch_size=8, num_epochs=1, max_steps=120, num_iterations=5,
                end_to_end=False, show_progress_bar=False,
                output_dir=str(Path(tmp) / "setfit-checkpoints"), report_to="none",
                save_strategy="no",
            )
            trainer = Trainer(model=model, args=args, train_dataset=data)
            trainer.train()
            model.save_pretrained(str(output))
        else:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments
            except ImportError as exc:
                raise RuntimeError("Установите опциональные зависимости ml-neural") from exc
            path = _base_path(engine)
            tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(
                path, num_labels=2, local_files_only=True, ignore_mismatched_sizes=True,
            )
            class BinaryData(torch.utils.data.Dataset):
                def __init__(self, texts, labels):
                    self.enc = tokenizer(texts, truncation=True, max_length=512, padding=True)
                    self.labels = labels
                def __len__(self):
                    return len(self.labels)
                def __getitem__(self, index):
                    return {**{k:torch.tensor(v[index]) for k,v in self.enc.items()},
                            "labels":torch.tensor(int(self.labels[index]),dtype=torch.long)}
            args = TrainingArguments(
                output_dir=str(Path(tmp)/"output"), num_train_epochs=2,
                max_steps=150, per_device_train_batch_size=8,
                save_strategy="no", eval_strategy="no", report_to="none",
                use_cpu=True, disable_tqdm=True,
            )
            Trainer(model=model, args=args, train_dataset=BinaryData(x_train,y_train)).train()
            model.save_pretrained(str(output), safe_serialization=True)
            tokenizer.save_pretrained(str(output))
        metrics = {
            "engine":engine, "labels":[category], "quality_gate_min_f1":min_f1,
            "split_sizes":{key:len(value[0]) for key,value in splits.items()},
            "base_model": "local-only",
        }
        thresholds = [.3,.4,.5,.6,.7]
        vx, vy = splits["validation"]
        if engine == "rubert":
            val_scores = _scores(engine, model, vx, tokenizer)
        else:
            val_scores = _scores(engine, model, vx)
        ranked=[]
        for cutoff in thresholds:
            p,r,f,_ = precision_recall_fscore_support(vy, val_scores>=cutoff, average="binary", zero_division=0)
            ranked.append((float(f),float(r),cutoff))
        threshold = max(ranked)[2]
        metrics["threshold"] = threshold
        for split in ("validation","test"):
            texts, targets = splits[split]
            scores = _scores(engine, model, texts, tokenizer if engine=="rubert" else None)
            p,r,f,s = precision_recall_fscore_support(targets, scores>=threshold,
                                                       average="binary", zero_division=0)
            metrics[split] = {category: {
                "precision":float(p),"recall":float(r),"f1":float(f),
                "support":int(sum(targets)),
            }}
        eligible = all(metrics[split][category]["f1"] >= min_f1 for split in ("validation","test"))
        artifact = _bundle(output,engine,category)
        return artifact,metrics,eligible


@lru_cache(maxsize=3)
def _load_binary(digest, artifact):
    import json

    _offline()
    folder = Path(tempfile.mkdtemp(prefix="mailfire-local-model-"))
    with zipfile.ZipFile(io.BytesIO(artifact)) as z:
        entries=z.namelist()
        if len(entries)>300 or any(not x.startswith(("model/","manifest.json")) or ".." in Path(x).parts for x in entries):
            raise ValueError("Некорректный архив модели")
        meta=json.loads(z.read("manifest.json"))
        if meta["engine"] not in {"setfit","rubert"}:
            raise ValueError("Неизвестный движок модели")
        if sum(item.file_size for item in z.infolist()) > MAX_ARTIFACT:
            raise ValueError("Превышен суммарный лимит распаковки модели")
        for item in z.infolist():
            if item.file_size>MAX_ARTIFACT:
                raise ValueError("Превышен лимит размера модели")
            if item.filename.startswith("model/") and not item.is_dir():
                dest=folder / item.filename
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(z.read(item))
    path=str(folder/"model")
    if meta["engine"]=="setfit":
        from setfit import SetFitModel
        return meta,SetFitModel.from_pretrained(path),None
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    return meta,AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True), AutoTokenizer.from_pretrained(path,local_files_only=True)


def infer_binary(artifact, text, category, threshold):
    if len(artifact)>MAX_ARTIFACT:
        raise ValueError("Модель превышает лимит")
    digest=hashlib.sha256(artifact).hexdigest()
    meta,model,tokenizer=_load_binary(digest,artifact)
    if meta["category"]!=category:
        raise ValueError("Модель относится к другой категории")
    score=float(_scores(meta["engine"],model,[text],tokenizer)[0])
    return {"category":category,"confidence":score,"threshold":threshold,
            "matched":score>=threshold,"uncertain":abs(score-threshold)<.1}
