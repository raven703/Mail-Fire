"""Portable Trainer packages. Inspection never deserializes model artifacts."""
import hashlib
import io
import json
import math
import re
import stat
import zipfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import PurePosixPath

MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_MANIFEST = 4 * 1024 * 1024
ENGINES = {"tfidf", "setfit", "rubert"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def versions():
    result = {}
    for name in ("numpy", "scikit-learn", "torch", "transformers", "setfit",
                 "sentence-transformers", "safetensors"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            pass
    return result


def check_versions(meta):
    required = {"numpy", "scikit-learn"}
    if meta["engine"] != "tfidf":
        required |= {"torch", "transformers", "safetensors"}
    if meta["engine"] == "setfit":
        required |= {"setfit", "sentence-transformers"}
    local = versions()
    for name in required:
        exported, installed = meta["versions"].get(name), local.get(name)
        if name == "torch":
            # Ignore only official CPU/CUDA wheel flavor labels, not arbitrary
            # local patches. Keep the complete public release (including rc/dev).
            exported = re.sub(r"\+(?:cpu|cu[0-9]+)$", "", exported) if isinstance(exported, str) else None
            installed = re.sub(r"\+(?:cpu|cu[0-9]+)$", "", installed) if isinstance(installed, str) else None
        if not exported or exported != installed:
            raise ValueError(f"Library version mismatch: {name}; use native dependency locks")


def validate_model(meta):
    if not isinstance(meta, dict) or meta.get("engine") not in ENGINES:
        raise ValueError("Invalid engine metadata")
    labels = meta.get("metrics", {}).get("labels")
    if (not isinstance(labels, list) or not labels or
            not all(isinstance(c, str) and c.strip() for c in labels) or len(set(labels)) != len(labels)):
        raise ValueError("Invalid category identifiers")
    if meta.get("categories") != labels:
        raise ValueError("Category metadata mismatch")
    if meta["engine"] == "tfidf":
        if meta.get("category_id") is not None or len(labels) < 2:
            raise ValueError("TF-IDF requires at least two categories and no category_id")
        thresholds = meta["metrics"].get("thresholds")
    else:
        if labels != [meta.get("category_id")]:
            raise ValueError("Binary model category mismatch")
        thresholds = [meta["metrics"].get("threshold")]
    if (not isinstance(thresholds, list) or len(thresholds) != len(labels) or
            any(type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds)):
        raise ValueError("Invalid thresholds")
    if meta.get("thresholds") != thresholds or type(meta.get("eligible")) is not bool:
        raise ValueError("Invalid quality gate or threshold metadata")
    if not isinstance(meta.get("versions"), dict):
        raise ValueError("Missing library versions")
    if meta.get("format", 1) != 1:
        raise ValueError("Unsupported model format")


def safe_entries(archive):
    entries = archive.infolist()
    names = [e.filename for e in entries]
    if len(entries) > MAX_ENTRIES or len(names) != len(set(names)):
        raise ValueError("Too many or duplicate ZIP entries")
    total = 0
    for entry in entries:
        name = entry.filename
        path = PurePosixPath(name)
        if (not name or name.startswith("/") or "\\" in name or ":" in name or
                any(p in ("", ".", "..") for p in name.rstrip("/").split("/")) or
                stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1):
            raise ValueError("Unsafe ZIP entry")
        if path.is_absolute() or entry.file_size > MAX_FILE:
            raise ValueError("ZIP file too large")
        total += entry.file_size
    if total > MAX_TOTAL:
        raise ValueError("ZIP expanded size exceeds limit")
    return entries


def inspect_package(source):
    try:
        with zipfile.ZipFile(source) as archive:
            entries = safe_entries(archive)
            if archive.getinfo("manifest.json").file_size > MAX_MANIFEST:
                raise ValueError("Manifest too large")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != 1 or not isinstance(manifest.get("models"), list) or not manifest["models"]:
                raise ValueError("Unsupported package format")
            expected = {"manifest.json", "report.json"}
            ids = set()
            for meta in manifest["models"]:
                validate_model(meta)
                ident = meta.get("id")
                if not isinstance(ident, str) or not ident.isascii() or not ident.isalnum() or ident in ids:
                    raise ValueError("Invalid or duplicate model id")
                ids.add(ident)
                suffix = "pkl" if meta["engine"] == "tfidf" else "zip"
                filename = f"models/{ident}/model.{suffix}"
                if meta.get("artifact") != filename:
                    raise ValueError("Invalid artifact path")
                expected.add(filename)
                raw = archive.read(filename)
                if digest(raw) != meta.get("artifact_sha256"):
                    raise ValueError("Artifact SHA-256 mismatch")
                if suffix == "zip":
                    with zipfile.ZipFile(io.BytesIO(raw)) as nested:
                        inner = safe_entries(nested)
                        if len(inner) > 300 or any(not e.filename.startswith(("model/", "manifest.json")) for e in inner):
                            raise ValueError("Invalid native neural ZIP layout")
            if set(e.filename for e in entries) != expected:
                raise ValueError("Unexpected or missing package files")
            if archive.getinfo("report.json").file_size > MAX_MANIFEST:
                raise ValueError("Report too large")
            report = archive.read("report.json")
            if digest(report) != manifest.get("report_sha256"):
                raise ValueError("Report SHA-256 mismatch")
            json.loads(report)
            return manifest
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError, UnicodeError, RuntimeError, NotImplementedError) as exc:
        raise ValueError(f"Invalid Trainer ZIP: {exc}") from exc


def write_package(path, models, report):
    """Include only explicit final artifacts, never datasets or checkpoints."""
    report_raw = json.dumps(report, ensure_ascii=False, allow_nan=False).encode()
    manifest = {"format": 1, "models": [], "report_sha256": digest(report_raw)}
    with path.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (metadata, raw) in enumerate(models, 1):
            meta = dict(metadata, id=f"m{index}")
            suffix = "pkl" if meta["engine"] == "tfidf" else "zip"
            meta.update(artifact=f"models/m{index}/model.{suffix}", artifact_sha256=digest(raw))
            validate_model(meta)
            manifest["models"].append(meta)
            archive.writestr(meta["artifact"], raw)
        archive.writestr("report.json", report_raw)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, allow_nan=False))
    inspect_package(path)
    return manifest