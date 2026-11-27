"""Resolve exact upstream metadata, save source references, never execute remote code."""
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path.home() / "hf-model-benchmark-data"
MODELS = {
    "horizon": "Horizon-Labs/multilingual-zeroshot-base",
    "mdeberta": "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
    "redmadrobot": "redmadrobot-rnd/rubert-base-pii-ner",
    "sciencesoft": "ScienceSoft/scnsoft-pii-encoder",
    "gloomreach": "Gloomreach/ru-toxicity-encoder",
    "phishing": "Aleksandr505/phishing-text-classifier-rubert",
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def main():
    output = HERE / "results" / "model_audit.json"
    if output.exists():
        raise FileExistsError(output)
    rows = {}
    for key, repo in MODELS.items():
        try:
            info = json.loads(fetch(f"https://huggingface.co/api/models/{repo}"))
            rev = info["sha"]
            config_raw = fetch(f"https://huggingface.co/{repo}/resolve/{rev}/config.json")
            card = fetch(f"https://huggingface.co/{repo}/resolve/{rev}/README.md").decode()
            folder = DATA / "metadata" / key
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "README.md").write_text(card)
            (folder / "config.json").write_bytes(config_raw)
            siblings = [item["rfilename"] for item in info["siblings"]]
            row = dict(repo=repo, revision=rev, available=True, gated=info.get("gated"),
                       license=info.get("cardData", {}).get("license", "unspecified"),
                       library=info.get("library_name"), task=info.get("pipeline_tag"),
                       config=json.loads(config_raw), files=siblings,
                       card_url=f"https://huggingface.co/{repo}/blob/{rev}/README.md")
            if key == "sciencesoft":
                row.update(status="blocked_gpu", reason="Only int8 ONNX CPU artifact; no PyTorch weights. No conversion, CPU fallback or weight modification permitted.",
                           license_note="Proprietary: evaluation allowed; no production, redistribution or modification license")
            elif key == "gloomreach":
                row.update(status="custom_adapter", reason="Three independent sigmoid heads; use reviewed local implementation, strict full checkpoint loading, no remote execution")
            else:
                row["status"] = "standard_transformers"
            if key == "phishing":
                row["license_note"] = "No model license specified; evaluation only, production legal review required"
            rows[key] = row
        except Exception as exc:
            rows[key] = dict(repo=repo, available=False, status="unavailable", reason=f"{type(exc).__name__}: {exc}")
        print(key, rows[key]["status"], flush=True)
    # The Gloomreach checkpoint contains the complete encoder; only architecture
    # config is used from the author's declared base, never substitute weights.
    info = json.loads(fetch("https://huggingface.co/api/models/cointegrated/rubert-tiny2"))
    rev = info["sha"]
    config = json.loads(fetch(f"https://huggingface.co/cointegrated/rubert-tiny2/resolve/{rev}/config.json"))
    rows["gloomreach"]["base_architecture"] = dict(repo="cointegrated/rubert-tiny2", revision=rev, config=config)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()