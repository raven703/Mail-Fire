"""Linux parser subprocess: resource limits, empty environment and denied network syscalls."""

import base64
import ctypes
import ctypes.util
import errno
import json
import os
import resource
import signal
import subprocess
import sys
import tempfile

from app.config import settings


def restrict(scan=False, unified=False):
    cpu_limit = 1200 if settings().ocr_backend == "surya" else 90
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    # Gitleaks' WASM regex runtime reserves 4GiB virtual memory; RSS remains
    # bounded by the parser container's 3GiB cgroup limit.
    address_limit = (8 if scan else 3) * 1024**3
    if settings().ocr_backend == "surya":
        address_limit = 24 * 1024**3
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
        blocked = (
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
        )
        if unified:
            blocked += ("setsid", "setpgid", "pidfd_open", "pidfd_getfd", "pidfd_send_signal",
                        "io_uring_setup", "io_uring_enter", "io_uring_register",
                        "kill", "tkill", "rt_sigqueueinfo", "rt_tgsigqueueinfo",
                        "process_madvise", "process_mrelease", "kcmp", "prlimit64",
                        "setpriority", "sched_setparam", "sched_setscheduler",
                        "sched_setaffinity", "sched_setattr", "migrate_pages", "move_pages",
                        "reboot", "kexec_load", "kexec_file_load", "bpf", "perf_event_open")
            # tgkill is required by threaded runtimes (Go included). Compare its
            # target TGID to the calling process at runtime; an inherited filter
            # with a fixed parent's PID would break exec'ed Go helpers. Until a
            # trusted helper supervisor exists, fail closed rather than allow
            # cross-process thread signals.
            blocked += ("tgkill",)
        for name in blocked:
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


def local_call(operation, data, name="", *, provider=None, force_ocr=False, isolated=False, timeout=None):
    if operation == 'regex':
        from app.analysis_ipc import helper_gateway
        if helper_gateway is not None:
            return helper_gateway(operation, data, name)
    payload = json.dumps(
        {"operation": operation, "data": base64.b64encode(data).decode(), "name": name,
         "force_ocr": force_ocr}
    ).encode()
    with tempfile.TemporaryDirectory(prefix="mailfire-parser-") as directory:
        env = {
            "PATH": os.path.dirname(sys.executable) + ":/usr/local/bin:/usr/bin:/bin",
            "HOME": directory,
            "TMPDIR": directory,
            "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parent.parent),
            "OPENBLAS_NUM_THREADS": "1" if isolated else "4",
            "OMP_NUM_THREADS": "1" if isolated else "4",
            "OCR_BACKEND": provider or settings().ocr_backend,
            "OCR_MODEL_ROOT": settings().ocr_model_root,
            **({'MICE_ISOLATED_HELPER': 'true'} if isolated else {}),
        }
        for key in ("TORCH_DEVICE", "DETECTOR_MODEL_CHECKPOINT", "RECOGNITION_MODEL_CHECKPOINT",
                    "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "DISABLE_TQDM"):
            if key in os.environ:
                env[key] = os.environ[key]
        with tempfile.TemporaryFile() as output_file, tempfile.TemporaryFile() as error_file:
            lifetime_read, lifetime_write = os.pipe()
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.helper_guardian", str(lifetime_read)] if isolated else [sys.executable, "-m", "app.sandbox"],
                    stdin=subprocess.PIPE,
                    stdout=output_file,
                    stderr=error_file,
                    env=env,
                    cwd=directory,
                    close_fds=True,
                    pass_fds=(lifetime_read,) if isolated else (),
                    start_new_session=True,
                )
            except BaseException:
                os.close(lifetime_write)
                raise
            finally:
                os.close(lifetime_read)
            try:
                maximum = 2 if operation == 'regex' else 35 if operation == 'gitleaks' else settings().analysis_timeout
                process.communicate(payload, timeout=maximum if timeout is None else min(maximum, max(.001, timeout)))
            finally:
                # Trusted owner kills the entire helper group, including escaped
                # subprocess lifetime after successful root exit or timeout.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                os.close(lifetime_write)
            result = process
            output_file.seek(0)
            output_bytes = output_file.read(settings().parser_response_bytes + 1)
    if result.returncode:
        raise RuntimeError("Parser sandbox failed")
    if len(output_bytes) > settings().parser_response_bytes:
        raise ValueError("Parser output limit")
    output = json.loads(output_bytes)
    if isinstance(output, dict) and output.get("error"):
        raise ValueError(output["error"])
    if operation == "mail":
        for attachment in output["attachments"]:
            attachment[2] = base64.b64decode(attachment[2], validate=True)
    return output


def main():
    request = json.loads(sys.stdin.buffer.read(70 * 1024**2))
    isolated = os.environ.get('MICE_ISOLATED_HELPER') == 'true'
    if isolated:
        from app.analysis_isolation import confine
        confine(os.getcwd())
    restrict(scan=request.get("operation") in {"scan", "scan_configured", "extract", "gitleaks"}, unified=isolated)
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
        elif request["operation"] == "regex":
            from app.categories import safe_regex

            output = []
            for match in safe_regex(request["name"]).finditer(data.decode()):
                output.append([match.start(), match.end()])
                if len(output) >= 10:
                    break
        elif request["operation"] == "dataset_import":
            from app.datasets import parse_dataset

            payload = json.loads(data)
            output = {"rows": parse_dataset(payload["text"].encode(), payload["name"], payload["category_map"])}
        elif request["operation"] == "upload_members":
            from app.uploads import upload_members

            output = {"members": [
                [name, base64.b64encode(value).decode()]
                for name, value in upload_members(data, request["name"])
            ]}
        elif request["operation"] == "gitleaks":
            from app.secret_scan import scan
            output = scan(data)
        elif request["operation"] in {"scan", "scan_configured"}:
            from app.advanced_detectors import static_scan

            if request["operation"] == "scan_configured":
                configured = json.loads(data)
                engines = configured["engines"]
                if set(engines) != {"static_files", "secrets"} or any(type(v) is not bool for v in engines.values()):
                    raise ValueError("Invalid scan engines")
                output = static_scan(base64.b64decode(configured["data"], validate=True), configured["name"], engines=engines)
            else:
                output = static_scan(data, request["name"])
        elif request["operation"] == "detection_evidence":
            from app.detection_evidence import analyze

            output = analyze(json.loads(data))
        elif request["operation"] == "detect":
            from app.advanced_detectors import pii
            from app.detectors import VERSION, detect

            text = data.decode("utf-8")
            output = {"findings": detect(text) + pii(text), "version": VERSION}
        elif request["operation"] == "mail":
            from app.mail import parse_mail

            output = parse_mail(data)
            output["attachments"] = [
                [name, mime, base64.b64encode(value).decode()] for name, mime, value in output["attachments"]
            ]
        elif request["operation"] == "preview":
            from app.document_preview import render

            output = render(data, request["name"])
        elif request["operation"] in {"extract", "extract_native"}:
            from app.extraction import extract

            text, status, details = extract(
                data, request["name"], use_ocr=request["operation"] != "extract_native",
                force_ocr=request.get("force_ocr") is True,
            )
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
