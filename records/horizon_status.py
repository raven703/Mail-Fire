"""No model imports/loads in HTTP: configured != tested or worker-ready."""

from django.utils import timezone

from pipeline.inference import enabled
from pipeline.models import WorkItem
from pipeline.resources import service_state
from records.models import CategoryRule, Metric, Setting


def horizon_status(flags):
    from app.horizon import MODEL

    configured = flags.get("horizon", False)
    gate = enabled("horizon")
    count = CategoryRule.objects.filter(
        kind="horizon", enabled=True, category__active=True, deleted_at__isnull=True
    ).count()
    sample = (
        Metric.objects.filter(service="neural", values__has_key="sample_at")
        .order_by("-created_at", "-pk")
        .first()
    )
    worker = service_state(sample, timezone.now())
    latest = WorkItem.objects.filter(kind="horizon.infer").order_by("-created_at", "-pk").first()
    tested = bool(latest and latest.status == "DONE" and latest.output.get("status") == "OK")
    # Web and worker have different filesystems: only worker results are evidence.
    local_files = None
    options = Setting.objects.filter(pk="horizon_detection").first()
    device = (options.value if options else {}).get("device", "cpu")
    label = (
        "Отключён"
        if not configured or not gate
        else "Нет включённых правил"
        if not count
        else "Worker не подтверждён"
        if worker not in {"ready", "running"}
        else "Последний анализ успешен (не гарантия текущей доступности)"
        if tested
        else "Модель не проверена успешным анализом"
    )
    return dict(
        label=label,
        configured=configured,
        gate=gate,
        rules=count,
        worker=worker,
        tested=tested,
        local_files=local_files,
        model=MODEL,
        last_job=latest.status if latest else "Нет заданий",
        device=device,
        error="GPU/Horizon недоступен или анализ неполный; проверьте worker и выберите CPU" if latest and latest.output.get("status") == "PARTIAL" else "",
    )
