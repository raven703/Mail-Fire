"""Bounded in-memory ZIP import; archive paths are never written to disk."""

import io
import stat
import zipfile
from pathlib import PurePosixPath


def upload_members(data, name, *, limits=None):
    if limits is None:
        from app.config import settings

        limits = settings()
    if len(data) > limits.max_message_bytes:
        raise ValueError("Upload size limit")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return [(name, data)]
    result, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > limits.max_objects:
            raise ValueError("Archive member count limit")
        for info in members:
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or ":" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError("Unsafe archive path")
            if info.is_dir():
                continue
            if info.flag_bits & 1:
                raise ValueError("Encrypted archive")
            if path.suffix.lower() not in {".eml", ".msg"}:
                raise ValueError("ZIP must contain only EML/MSG files")
            total += info.file_size
            if (
                total > limits.max_expanded_bytes
                or info.file_size > limits.max_message_bytes
                or info.file_size > max(info.compress_size, 1) * 200
            ):
                raise ValueError("Archive expansion limit")
            with archive.open(info) as stream:
                payload = stream.read(limits.max_message_bytes + 1)
            if len(payload) != info.file_size:
                raise ValueError("Invalid archive size")
            result.append((info.filename, payload))
    if not result:
        raise ValueError("Empty archive")
    if len({name for name, _ in result}) != len(result):
        raise ValueError("Duplicate archive member")
    return result
