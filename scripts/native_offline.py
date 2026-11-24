"""Export/import experimental images with checksums; never starts containers.

Run on a trusted build host after building all desired optional profiles.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ["runtime", "parser", "ocr", "converter", "web", "training", "semantic"]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def export(destination, neural_models=None):
    destination.mkdir(parents=True, exist_ok=False)
    names = [f"mice-{name}:latest" for name in IMAGES]
    if neural_models:
        names.append("mice-neural:latest")
    names += ["pgvector/pgvector:pg17", "rabbitmq:4.2-management"]
    manifest = {"schema_version": 1, "images": [], "files": {}}
    for index, name in enumerate(names):
        identity = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", name], text=True).strip()
        filename = f"image-{index:02d}.tar"
        subprocess.run(["docker", "image", "save", "--output", str(destination / filename), name], check=True)
        manifest["images"].append({"name": name, "id": identity, "file": filename})
        manifest["files"][filename] = digest(destination / filename)
    filename = "compose.yaml"
    compose = (ROOT / filename).read_text()
    probe = "native_resource_probe.sh"
    shutil.copyfile(ROOT / "scripts" / probe, destination / probe)
    manifest["files"][probe] = digest(destination / probe)
    (destination / filename).write_text(compose.replace("./scripts/" + probe, "./" + probe))
    manifest["files"][filename] = digest(destination / filename)
    if neural_models:
        for relative in ["rubert/config.json", "setfit/modules.json"]:
            if not (neural_models / relative).is_file():
                raise ValueError("Missing local model metadata: " + relative)
        archive = destination / "neural-models.tar"
        with tarfile.open(archive, "w") as output:
            for path in sorted(neural_models.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Model symlinks must be materialized before export")
                if path.is_file():
                    output.add(path, arcname=str(path.relative_to(neural_models)), recursive=False)
        manifest["files"][archive.name] = digest(archive)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify(source, load=False, restore_models=None):
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported offline manifest")
    for filename, expected in manifest["files"].items():
        if Path(filename).name != filename or (source / filename).is_symlink():
            raise ValueError("Unsafe bundle filename")
        if digest(source / filename) != expected:
            raise ValueError("Checksum mismatch: " + filename)
    for image in manifest["images"]:
        if image["file"] not in manifest["files"]:
            raise ValueError("Unchecked image")
    if restore_models is not None:
        if "neural-models.tar" not in manifest["files"]:
            raise ValueError("No verified local models in bundle")
        restore_local_models(source / "neural-models.tar", restore_models)
    if load:
        for image in manifest["images"]:
            subprocess.run(["docker", "image", "load", "--input", str(source / image["file"])], check=True)
            actual = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image["name"]], text=True).strip()
            if actual != image["id"]:
                raise ValueError("Loaded image identity mismatch")


def restore_local_models(archive, destination):
    """Extract regular files only, stage privately, publish a new directory atomically."""
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Model destination must not exist")
    if not destination.parent.is_dir():
        raise ValueError("Model destination parent must exist")
    with tarfile.open(archive, "r") as source:
        members = source.getmembers()
        names = set()
        total = 0
        for member in members:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in names or not path.parts or path.parts[0] not in {"rubert", "setfit"}:
                raise ValueError("Unsafe local model archive member")
            names.add(member.name)
            total += member.size
        if len(members) > 100000 or total > 40 * 1024**3:
            raise ValueError("Local model archive exceeds restore limit")
        if not {"rubert/config.json", "setfit/modules.json"} <= names:
            raise ValueError("Incomplete local model archive")
        stage = Path(tempfile.mkdtemp(prefix=".mice-models-", dir=destination.parent))
        try:
            for member in members:
                target = stage / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)
                target.chmod(0o644)
            stage.chmod(0o755)
            # mkdir reserves the destination; no replacement of existing models.
            destination.mkdir()
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "verify", "load"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--neural-models", type=Path, help="Include neural image and materialized local model snapshots")
    parser.add_argument("--restore-models", type=Path, help="Restore verified local models into a NEW directory")
    args = parser.parse_args()
    if args.action == "export":
        export(args.directory, args.neural_models)
    else:
        verify(args.directory, args.action == "load", args.restore_models)