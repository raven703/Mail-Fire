"""Read-only directory ingestion; stable files, no symlink traversal or mutations."""

import hashlib
import os
import stat
import time
from pathlib import Path

from django.conf import settings

from pipeline.ingestion import accept
from records.models import ImportRecord


def signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_message(root_fd, parts):
    directory = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= settings.MICE_MAX_MESSAGE_BYTES:
                raise ValueError("Invalid directory message")
            data = stream.read(settings.MICE_MAX_MESSAGE_BYTES + 1)
            after = os.fstat(stream.fileno())
        if signature(before) != signature(after) or len(data) != before.st_size:
            raise ValueError("File changed during read")
        return data, after
    finally:
        os.close(directory)


def scan(root, observed, *, namespace, recursive=True, stability_seconds=5, now=None):
    if not namespace or len(namespace) > 128:
        raise ValueError("A stable import namespace is required")
    if stability_seconds < 0:
        raise ValueError("Invalid stability interval")
    root = Path(root).resolve(strict=True)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    now = time.monotonic() if now is None else now
    counts = {"accepted": 0, "waiting": 0, "failed": 0}
    seen = set()
    try:
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs
                if recursive and name != ".imported" and not (Path(directory) / name).is_symlink()
            )
            for name in sorted(files):
                path = Path(directory) / name
                if path.suffix.lower() not in {".eml", ".msg"} or path.is_symlink():
                    continue
                relative = path.relative_to(root)
                key = relative.as_posix()
                seen.add(key)
                current = None
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    current = signature(info)
                    previous = observed.get(key)
                    if previous is None or previous[0] != current:
                        observed[key] = (current, now, False)
                        counts["waiting"] += 1
                        continue
                    if previous[2]:
                        continue
                    if now - previous[1] < stability_seconds:
                        counts["waiting"] += 1
                        continue
                    data, after = read_message(root_fd, relative.parts)
                    if signature(after) != current:
                        counts["waiting"] += 1
                        continue
                    # Root location may change, logical source namespace must not.
                    identity = hashlib.sha256(
                        f"{namespace}\0{key}\0{hashlib.sha256(data).hexdigest()}".encode()
                    ).hexdigest()
                    accept(data, "folder", "file:" + identity, key)
                    observed[key] = (current, previous[1], True)
                    counts["accepted"] += 1
                except (OSError, ValueError) as exc:
                    counts["failed"] += 1
                    fingerprint = hashlib.sha256(
                        f"{namespace}\0{key}\0{current}".encode(),
                    ).hexdigest()
                    ImportRecord.objects.get_or_create(
                        source_key="file-failed:" + fingerprint,
                        defaults={"name": key, "status": "FAILED", "error": type(exc).__name__},
                    )
        for key in set(observed) - seen:
            del observed[key]
    finally:
        os.close(root_fd)
    return counts
