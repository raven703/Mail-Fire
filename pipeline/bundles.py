"""Durable ZIP intake; expansion runs only inside the secret-free parser sandbox."""

import base64
import hashlib
from pathlib import PurePosixPath

from django.conf import settings
from django.db import transaction

from pipeline.ingestion import accept
from pipeline.parser_client import call
from pipeline.services import enqueue, finish, locked_current
from records.models import Blob


@transaction.atomic
def accept_bundle(data, source_key, name):
    if not 0 < len(data) <= settings.MICE_MAX_MESSAGE_BYTES:
        raise ValueError("Invalid upload size")
    digest = hashlib.sha256(data).hexdigest()
    Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
    return enqueue(
        "ingestion.bundle",
        {"blob_sha": digest, "source_key": source_key, "name": name[:1024]},
        "bundle:" + hashlib.sha256(source_key.encode()).hexdigest(),
    )


def expand_bundle(job):
    blob = Blob.objects.get(pk=job.payload["blob_sha"])
    result = call("upload_members", bytes(blob.data), job.payload["name"])
    members = result.get("members")
    if not isinstance(members, list) or not 0 < len(members) <= settings.MICE_IMPORT_MAX_OBJECTS:
        raise ValueError("Invalid bundle response")
    decoded, total, names = [], 0, set()
    for name, encoded in members:
        path = PurePosixPath(name)
        if (
            not name or len(name) > 1024 or path.is_absolute() or ".." in path.parts
            or "\\" in name or ":" in name or name in names
            or path.suffix.lower() not in {".eml", ".msg"}
        ):
            raise ValueError("Invalid bundle member")
        data = base64.b64decode(encoded, validate=True)
        total += len(data)
        if not 0 < len(data) <= settings.MICE_MAX_MESSAGE_BYTES or total > settings.MICE_IMPORT_MAX_BYTES:
            raise ValueError("Bundle expansion limit")
        names.add(name)
        decoded.append((name, data))
    # All-or-nothing acceptance; retries cannot create extra delivery events.
    with transaction.atomic():
        locked_current(job.pk, job.token)
        ids = []
        for index, (name, data) in enumerate(decoded):
            key = "bundle-member:" + hashlib.sha256(
                f"{job.payload['source_key']}:{index}:{name}".encode()
            ).hexdigest()
            record = accept(data, "upload", key, name)
            ids.append(record.message_id)
        finish(job.pk, job.token, {"message_ids": ids, "accepted": len(ids)})