"""Install a pinned upstream binary, verified before extraction (linux amd64)."""

import hashlib
import io
import platform
import tarfile
import urllib.request
from pathlib import Path

if platform.machine() not in {"x86_64", "amd64"}:
    raise RuntimeError("Pinned Gitleaks artifact requires linux amd64")
url = "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz"
with urllib.request.urlopen(url, timeout=120) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb":
    raise RuntimeError("Gitleaks checksum mismatch")
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    binary = archive.extractfile("gitleaks").read()
target = Path("/usr/local/bin/gitleaks")
target.write_bytes(binary)
target.chmod(0o755)
