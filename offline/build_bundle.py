"""Build a portable bundle from explicitly selected, existing local images/assets."""
import hashlib
import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "dist" / "MICE-offline-linux-amd64"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def build():
    STAGE.mkdir(parents=True, exist_ok=False)
    for p in (ROOT / "offline").glob("*.sh"):
        shutil.copy2(p, STAGE / p.name)
        (STAGE / p.name).chmod(0o755)
    shutil.copy2(ROOT / "offline/restore_config.py", STAGE)
    shutil.copy2(ROOT / "offline/README.md", STAGE)
    shutil.copy2(ROOT / "scripts/native_resource_probe.sh", STAGE)
    script = (ROOT / "offline/export_config.py").read_text()
    wrapper = 'import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE","mice.settings"); import django; django.setup(); exec(' + repr(script) + ')'
    with (STAGE / "config.json").open("w") as output:
        run("docker", "exec", "mice-web-1", "python", "-c", wrapper, stdout=output)
    json.loads((STAGE / "config.json").read_text())
    compose = json.loads(subprocess.check_output(
        ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "--profile", "*", "config", "--format", "json", "--no-interpolate"], cwd=ROOT))
    enabled = {"db", "rabbitmq", "migrate", "parser", "ocr-parser", "converter", "web", "frontend",
               "publisher", "beat", "ingestion", "analysis", "extraction", "ocr", "detection", "policy",
               "notifications", "maintenance", "neural", "ml", "training", "ocr-surya"}
    compose.pop("name", None)
    compose["services"] = {k: v for k, v in compose["services"].items() if k in enabled}
    images = {}
    for name, service in compose["services"].items():
        service.pop("build", None)
        service.pop("profiles", None)
        service["pull_policy"] = "never"
        service["platform"] = "linux/amd64"
        original = service["image"]
        if original == "mice-training:latest":
            original = "horizon-pr39-training:validation"
        identity = json.loads(subprocess.check_output(["docker", "image", "inspect", original]))[0]
        assert identity["Architecture"] == "amd64"
        tag = "mice-offline/" + name + ":" + identity["Id"][7:19]
        run("docker", "tag", identity["Id"], tag)
        images[tag] = identity["Id"]
        service["image"] = tag
        service.pop("ports", None)
        if name == "frontend":
            service["ports"] = ["127.0.0.1:18080:8080"]
        env = service.get("environment", {})
        for key, value in list(env.items()):
            if key in {"DJANGO_SECRET_KEY", "MICE_DB_PASSWORD", "ADMIN_PASSWORD", "MICE_RABBIT_PASSWORD", "POSTGRES_PASSWORD", "RABBITMQ_DEFAULT_PASS"}:
                source = {"POSTGRES_PASSWORD": "MICE_DB_PASSWORD", "RABBITMQ_DEFAULT_PASS": "MICE_RABBIT_PASSWORD"}.get(key, key)
                env[key] = "${" + source + "}"
        env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"})
        if "MICE_DB_HOST" in env:
            env["MICE_UNIFIED_ANALYSIS_ENABLED"] = "true"
            env["MICE_HORIZON_INFERENCE_ENABLED"] = "true"
        if name == "web":
            env["MICE_COOKIE_SECURE"] = "false"
        service["environment"] = env
        for volume in service.get("volumes", []):
            if volume["target"] == "/opt/neural-models":
                volume.clear()
                volume.update({"type": "bind", "source": "./models/neural", "target": "/opt/neural-models", "read_only": True})
            if volume["type"] == "bind":
                volume["source"] = "./models/horizon" if volume["target"] == "/opt/horizon" else "./models/neural"
        if name == "migrate":
            service.setdefault("volumes", []).append({"type": "bind", "source": ".", "target": "/bundle", "read_only": True})
    compose["configs"]["resource-probe"]["file"] = "./native_resource_probe.sh"
    compose.setdefault("networks", {})["default"] = {"internal": True}
    for net in compose["networks"].values():
        net.pop("name", None)
        net["internal"] = True
    # Docker does not publish ports on an internal-only network. Only nginx
    # joins this edge network; application workers remain without egress.
    compose["networks"]["edge"] = {"internal": False}
    compose["services"]["frontend"]["networks"] = {"default": None, "edge": None}
    for volume in compose["volumes"].values():
        if volume:
            volume.pop("name", None)
    (STAGE / "compose.offline.json").write_text(json.dumps(compose, indent=2))
    for name, source in {"horizon": "/home/user/horizon-pr39-assets/checkpoint",
                         "neural/rubert": "/home/user/Mice-ml-models/rubert",
                         "neural/setfit": "/home/user/Mice-ml-models/setfit"}.items():
        shutil.copytree(source, STAGE / "models" / name, symlinks=False,
                        ignore=shutil.ignore_patterns(".git", ".cache", "__pycache__", "training.json", "training", "eval"))
    for name in ("rubert", "setfit"):
        with zipfile.ZipFile(STAGE / f"models/neural/{name}/pack-ru2-financial-plans/model.zip") as archive:
            for member in archive.namelist():
                if member.startswith("model/") and not member.endswith("/"):
                    relative = Path(member).relative_to("model")
                    if ".." in relative.parts:
                        raise ValueError("Unsafe model member")
                    target = STAGE / f"models/neural/base-{name}" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
    (STAGE / "manifest.json").write_text(json.dumps({"images": images, "engine": "29.6.1", "compose": "5.3.0"}, indent=2))
    run("docker", "save", "-o", str(STAGE / "images.tar"), *images)
    with (STAGE / "SHA256SUMS").open("w") as f:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                f.write(sha(path) + "  " + str(path.relative_to(STAGE)) + "\n")
    archive = ROOT / "dist/MICE-offline-linux-amd64.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=1) as tar:
        tar.add(STAGE, arcname=STAGE.name, filter=lambda member: None if Path(member.name).name == ".env" else member)
    (ROOT / "dist/MICE-offline-linux-amd64.tar.gz.sha256").write_text(sha(archive) + "  " + archive.name + "\n")
    print(archive, archive.stat().st_size, sha(archive), flush=True)


if __name__ == "__main__":
    build()