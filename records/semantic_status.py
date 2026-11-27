"""Read-only semantic readiness based on stored index and resource samples."""
from django.db.models import Count
from django.utils import timezone
from pipeline.resources import service_state
from pipeline.inference import enabled
from pipeline.semantic_detection import threshold
from records.models import Category, Metric, Reference, SemanticChunk
from records.semantic import MODEL


def semantic_status(flags, options=None):
    ordinary = Reference.objects.exclude(fingerprint__has_key="document_template")
    total = ordinary.count()
    indexed = SemanticChunk.objects.filter(source_type="reference", model=MODEL,
                                         source_id__in=ordinary.values("pk")).values("source_id").distinct().count()
    sample = Metric.objects.filter(service="semantic", values__has_key="sample_at").order_by("-created_at", "-pk").first()
    worker = service_state(sample, timezone.now())
    worker_label = {"ready": "Доступен по последнему замеру", "running": "Поступают замеры",
                    "missing": "Нет замеров", "stale": "Замеры устарели",
                    "degraded": "Проверка не прошла", "completed": "Завершён"}.get(worker, "Не подтверждён")
    category_active = Category.objects.filter(pk="SEMANTIC_REFERENCE", active=True).exists()
    gate = enabled("semantic")
    try:
        minimum = threshold(options)
    except (ValueError, TypeError):
        minimum = None
    if not flags.get("semantic", True) or not category_active or not gate:
        label = "Отключён"
    elif not total:
        label = "Нет эталонов"
    elif not indexed:
        label = "Требуется индексация"
    elif minimum is None:
        label = "Некорректный порог"
    elif worker not in {"ready", "running"}:
        label = "Доступность worker не подтверждена"
    elif indexed < total:
        label = "Индекс неполный"
    else:
        label = "Условия выполнены"
    return {"label": label, "total": total, "indexed": indexed, "worker_label": worker_label,
            "gate": gate, "category_active": category_active, "threshold": minimum,
            "configured": flags.get("semantic", True)}
