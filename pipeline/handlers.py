"""Explicit runnable handlers. Unported analysis stages are never fake-success tasks."""

import os
import socket

import psutil
from django.db import transaction

from pipeline.services import finish, locked_current, recover
from records.models import Metric


def sample_resources(job):
    memory = psutil.virtual_memory()
    values = {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_used": memory.used,
        "ram_total": memory.total,
        "swap_used": psutil.swap_memory().used,
        "disk_free": psutil.disk_usage("/").free,
        "process_rss": psutil.Process().memory_info().rss,
        "scope": "worker-visible-system",
        "gpu": None,
    }
    with transaction.atomic():
        locked_current(job.pk, job.token)
        Metric.objects.create(service="celery:" + socket.gethostname(), values=values)
        finish(job.pk, job.token, {"sampled": True})


def recover_deliveries(job):
    with transaction.atomic():
        locked_current(job.pk, job.token)
        count = recover()
        finish(job.pk, job.token, {"recovered": count})


def evaluate_policy(job):
    from policy_engine.service import evaluate

    evaluate(job)


def parse_message(job):
    from pipeline.ingestion import parse

    parse(job)


def extract_message(job):
    from pipeline.extraction import extract

    extract(job)


def complete_ocr(job):
    from pipeline.ocr import complete

    complete(job)


def deliver_notification(job):
    from pipeline.notifications import deliver

    deliver(job)


handlers = {
    "ocr.complete": ("ocr", complete_ocr),
    "extraction.extract": ("extraction", extract_message),
    "ingestion.parse": ("ingestion", parse_message),
    "policy.evaluate": ("policy", evaluate_policy),
    "notifications.deliver": ("notifications", deliver_notification),
    "maintenance.resources": ("maintenance", sample_resources),
    "maintenance.recover": ("maintenance", recover_deliveries),
}
