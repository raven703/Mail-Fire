"""Export/import experimental images with checksums; never starts containers.

Run on a trusted build host after building all desired optional profiles.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ["runtime", "parser", "ocr", "converter", "web", "training", "semantic"]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def export(destination):
    destination.mkdir(parents=True, exist_ok=False)
    names = [f"mice-django-{name}:experiment" for name in IMAGES]
    names += ["pgvector/pgvector:pg17", "rabbitmq:4.2-management"]
    manifest = {"schema_version": 1, "images": [], "files": {}}
    for index, name in enumerate(names):
        identity = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", name], text=True).strip()
        filename = f"image-{index:02d}.tar"
        subprocess.run(["docker", "image", "save", "--output", str(destination / filename), name], check=True)
        manifest["images"].append({"name": name, "id": identity, "file": filename})
        manifest["files"][filename] = digest(destination / filename)
    filename = "compose.django.yaml"
    (destination / filename).write_bytes((ROOT / filename).read_bytes())
    manifest["files"][filename] = digest(destination / filename)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify(source, load=False):
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
    if load:
        for image in manifest["images"]:
            subprocess.run(["docker", "image", "load", "--input", str(source / image["file"])], check=True)
            actual = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image["name"]], text=True).strip()
            if actual != image["id"]:
                raise ValueError("Loaded image identity mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "verify", "load"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "export":
        export(args.directory)
    else:
        verify(args.directory, args.action == "load")