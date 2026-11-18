"""Linux parser subprocess: resource limits, empty environment and denied network syscalls."""

import base64
import ctypes
import ctypes.util
import errno
import json
import os
import resource
import subprocess
import sys
import tempfile

from app.config import settings


def restrict(scan=False):
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    # Gitleaks' WASM regex runtime reserves 4GiB virtual memory; RSS remains
    # bounded by the parser container's 3GiB cgroup limit.
    address_limit = (8 if scan else 3) * 1024**3
    resource.setrlimit(resource.RLIMIT_AS, (address_limit, address_limit))
    resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024**2, 128 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise RuntimeError("libseccomp is required; refusing unsafe parsing")
    lib = ctypes.CDLL(library)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("Cannot initialize seccomp")
    try:
        for name in (
            "socket",
            "socketpair",
            "connect",
            "bind",
            "listen",
            "accept",
            "accept4",
            "ptrace",
            "mount",
            "unshare",
            "setns",
            "process_vm_readv",
            "process_vm_writev",
        ):
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError("Cannot install seccomp rule")
        if lib.seccomp_load(context) != 0:
            raise RuntimeError("Cannot load seccomp policy")
    finally:
        lib.seccomp_release(context)


def call(operation, data, name=""):
    if not settings().parser_url:
        return local_call(operation, data, name)
    import httpx

    with httpx.Client(timeout=settings().analysis_timeout + 15, trust_env=False) as client:
        with client.stream(
            "POST",
            settings().parser_url + "/parse",
            json={"operation": operation, "data": base64.b64encode(data).decode(), "name": name},
        ) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_bytes():
                if len(payload) + len(chunk) > settings().parser_response_bytes:
                    raise ValueError("Parser response limit")
                payload.extend(chunk)
            output = json.loads(payload)
    if operation == "mail":
        for attachment in output["attachments"]:
            attachment[2] = base64.b64decode(attachment[2], validate=True)
    return output


def local_call(operation, data, name=""):
    payload = json.dumps(
        {"operation": operation, "data": base64.b64encode(data).decode(), "name": name}
    ).encode()
    with tempfile.TemporaryDirectory(prefix="mailfire-parser-") as directory:
        env = {
            "PATH": os.path.dirname(sys.executable) + ":/usr/local/bin:/usr/bin:/bin",
            "HOME": directory,
            "TMPDIR": directory,
            "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parent.parent),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OCR_BACKEND": settings().ocr_backend,
            "OCR_MODEL_ROOT": settings().ocr_model_root,
        }
        with tempfile.TemporaryFile() as output_file, tempfile.TemporaryFile() as error_file:
            result = subprocess.run(
                [sys.executable, "-m", "app.sandbox"],
                input=payload,
                stdout=output_file,
                stderr=error_file,
                env=env,
                cwd=directory,
                timeout=settings().analysis_timeout,
                close_fds=True,
            )
            output_file.seek(0)
            output_bytes = output_file.read(settings().parser_response_bytes + 1)
    if result.returncode:
        raise RuntimeError("Parser sandbox failed")
    if len(output_bytes) > settings().parser_response_bytes:
        raise ValueError("Parser output limit")
    output = json.loads(output_bytes)
    if output.get("error"):
        raise ValueError(output["error"])
    if operation == "mail":
        for attachment in output["attachments"]:
            attachment[2] = base64.b64decode(attachment[2], validate=True)
    return output


def main():
    request = json.loads(sys.stdin.buffer.read(70 * 1024**2))
    restrict(scan=request.get("operation") in {"scan", "extract"})
    data = base64.b64decode(request["data"], validate=True)
    try:
        if request["operation"] == "probe":
            import socket

            try:
                socket.socket()
            except PermissionError:
                from pathlib import Path

                sensitive = {}
                for path in ("/app/.env", "/var/run/docker.sock", "/imports", "/var/lib/postgresql/data"):
                    sensitive[path] = Path(path).exists()
                output = {
                    "network_denied": True,
                    "database_secret": os.getenv("DATABASE_URL"),
                    "sensitive_paths": sensitive,
                    "uid": os.getuid(),
                }
            else:
                raise RuntimeError("Network unexpectedly allowed")
        elif request["operation"] == "scan":
            from app.advanced_detectors import static_scan

            output = static_scan(data, request["name"])
        elif request["operation"] == "mail":
            from app.mail import parse_mail

            output = parse_mail(data)
            output["attachments"] = [
                [name, mime, base64.b64encode(value).decode()] for name, mime, value in output["attachments"]
            ]
        elif request["operation"] == "extract":
            from app.extraction import extract

            text, status, details = extract(data, request["name"])
            output = {"text": text, "status": status, "details": details}
        else:
            raise ValueError("Unknown sandbox operation")
    except Exception as exc:
        output = {"error": type(exc).__name__}
    encoded = json.dumps(output)
    if len(encoded.encode()) > settings().parser_response_bytes:
        raise ValueError("Parser response limit")
    sys.stdout.write(encoded)


if __name__ == "__main__":
    main()
