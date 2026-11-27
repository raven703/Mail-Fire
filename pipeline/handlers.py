"""Explicit runnable handlers. Unported analysis stages are never fake-success tasks."""

from django.db import connection, transaction
from django.utils import timezone

from pipeline.resource_history import latest_resource_samples
from pipeline.resources import HISTORY_FOR, SERVICES, collect_probes, cpu_usage
from pipeline.services import finish, locked_current, recover
from records.models import Metric


def sample_resources(job):
    now = timezone.now()
    probes = collect_probes(now)
    with transaction.atomic():
        locked_current(job.pk, job.token)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('mice-resource-sampler'))")
        previous = {row.service: row for row in latest_resource_samples()}
        samples = []
        for service, (recorded, values) in probes.items():
            last = previous.get(service)
            if last and last.values["sample_at"] >= values["sample_at"]:
                continue
            values["cpu_percent"] = cpu_usage(values, last.values if last else None)
            samples.append(Metric(service=service, created_at=recorded, values=values))
        Metric.objects.bulk_create(samples)
        expired = Metric.objects.filter(service__in=SERVICES, created_at__lt=now - HISTORY_FOR)
        expired.filter(pk__in=list(expired.order_by("created_at").values_list("pk", flat=True)[:1000])).delete()
        finish(job.pk, job.token, {"sampled": len(samples), "available": sorted(probes)})


def recover_deliveries(job):
    with transaction.atomic():
        locked_current(job.pk, job.token)
        count = recover()
        finish(job.pk, job.token, {"recovered": count})


def cleanup_retention(job):
    from records.retention import cleanup

    cleanup(job)


def evaluate_policy(job):
    from policy_engine.service import evaluate

    evaluate(job)


def reevaluate_batch(job):
    from policy_engine.service import reevaluate_batch as run

    run(job)


def parse_message(job):
    from pipeline.ingestion import parse

    parse(job)


def expand_bundle(job):
    from pipeline.bundles import expand_bundle as expand

    expand(job)


def extract_message(job):
    from pipeline.extraction import extract

    extract(job)


def detect_message(job):
    from pipeline.detection import detect

    detect(job)


def complete_ocr(job):
    from pipeline.ocr import complete

    complete(job)


def deliver_notification(job):
    from pipeline.notifications import deliver

    deliver(job)


def train_model(job):
    from records.model_management import train_job

    train_job(job)


def reindex_semantic(job):
    from records.semantic import reindex

    reindex(job)


def detect_semantic(job):
    from pipeline.semantic_detection import run

    run(job)


def search_semantic(job):
    from records.semantic import search_job

    search_job(job)


def collect_garbage(job):
    from records.garbage_collection import collect

    collect(job)


def infer_optional(job):
    from pipeline.inference import run

    run(job)


def analyze_message(job):
    from pipeline.analysis import analyze

    analyze(job)


handlers = {
    "analysis.analyze": ("analysis", analyze_message),
    "neural.infer": ("neural", infer_optional),
    "ml.infer": ("ml", infer_optional),
    "llm.infer": ("llm", infer_optional),
    "maintenance.gc": ("maintenance", collect_garbage),
    "semantic.reindex": ("semantic", reindex_semantic),
    "semantic.detect": ("semantic", detect_semantic),
    "semantic.search": ("semantic", search_semantic),
    "training.model": ("training", train_model),
    "training.neural": ("neural_training", train_model),
    "maintenance.retention": ("maintenance", cleanup_retention),
    "ingestion.bundle": ("ingestion", expand_bundle),
    "detection.detect": ("detection", detect_message),
    "ocr.complete": ("ocr", complete_ocr),
    "extraction.extract": ("extraction", extract_message),
    "ingestion.parse": ("ingestion", parse_message),
    "policy.evaluate": ("policy", evaluate_policy),
    "policy.reevaluate_batch": ("policy", reevaluate_batch),
    "notifications.deliver": ("notifications", deliver_notification),
    "maintenance.resources": ("maintenance", sample_resources),
    "maintenance.recover": ("maintenance", recover_deliveries),
}
