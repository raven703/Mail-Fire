import os
import stat
import time
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db import transaction
from app.mail import ingest, sha
from app.models import ImportRecord


def scan(root, observed):
    root = Path(root).resolve(strict=True)
    paths = root.rglob("*") if settings().import_recursive else root.iterdir()
    for path in paths:
        if path.is_symlink() or path.suffix.lower() not in {".eml", ".msg"}:
            continue
        try:
            if root not in path.resolve().parents:
                continue
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            signature = (info.st_size, info.st_mtime_ns)
            previous = observed.get(str(path))
            if not previous or previous[:2] != signature:
                observed[str(path)] = (*signature, time.monotonic())
                continue
            if time.monotonic() - previous[2] < settings().import_stability_seconds:
                continue
            if info.st_size > settings().max_message_bytes:
                raise ValueError("Message size limit")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                data = stream.read(settings().max_message_bytes + 1)
                after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                continue
            key = "file:" + str(path.relative_to(root)) + ":" + sha(data)
            with transaction() as session:
                record = ingest(session, data, "folder", key, str(path.relative_to(root)))
                success = record.status == "SAVED"
            if success and settings().import_policy == "delete":
                if path.stat().st_mtime_ns == after.st_mtime_ns:
                    path.unlink()
            elif success and settings().import_policy == "archive":
                # Remains within the explicitly user-managed source directory.
                destination = root / ".imported" / path.relative_to(root)
                if ".imported" not in path.relative_to(root).parts:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    path.rename(destination)
        except Exception as exc:
            key = "failed:" + str(path) + ":" + str(path.lstat().st_mtime_ns)
            with transaction() as session:
                if not session.scalar(select(ImportRecord).where(ImportRecord.source_key == key)):
                    session.add(
                        ImportRecord(
                            source_key=key, name=path.name, status="FAILED", error=type(exc).__name__
                        )
                    )


def main():
    observed = {}
    while True:
        try:
            scan(settings().import_root, observed)
        except Exception:
            pass  # Retry after transient database/source unavailability.
        time.sleep(5)


if __name__ == "__main__":
    main()
