from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from pipeline.models import WorkItem
from pipeline.monitoring import database_snapshot, flow_snapshot, snapshot
from pipeline.resources import local_resources
from pipeline.services import cancel, retry
from records.models import Audit, Diagnostic, Metric


def denied(request, admin=False):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    if not request.user.has_perm("identity.administer" if admin else "identity.access_mice"):
        return JsonResponse({"detail": "Недостаточно прав"}, status=403)
    return None


@require_GET
def monitor_api(request):
    error = denied(request)
    return error if error is not None else JsonResponse(snapshot())


@require_GET
def operations(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    error = denied(request)
    if error is not None:
        return error
    jobs = WorkItem.objects.order_by("-created_at")
    status, queue = request.GET.get("status", ""), request.GET.get("queue", "")
    if status:
        jobs = jobs.filter(status=status)
    if queue:
        jobs = jobs.filter(queue=queue)
    return render(
        request,
        "pipeline/operations.html",
        {
            "monitor": snapshot(),
            "local_resources": local_resources(),
            "flow": flow_snapshot(),
            "database": database_snapshot() if request.user.has_perm("identity.administer") else None,
            "jobs": jobs[:100],
            "metrics": Metric.objects.filter(service__startswith="celery:").order_by("-created_at")[:10],
            "can_administer": request.user.has_perm("identity.administer"),
            "diagnostics": Diagnostic.objects.order_by("-created_at").values("created_at", "service", "level", "event")[:30],
        },
    )


@require_POST
@transaction.atomic
def control(request, job_id, action):
    error = denied(request, admin=True)
    if error is not None:
        return error
    try:
        if action not in {"retry", "cancel"}:
            return JsonResponse({"detail": "Неизвестное действие"}, status=404)
        job = (retry if action == "retry" else cancel)(job_id)
    except WorkItem.DoesNotExist:
        return JsonResponse({"detail": "Задание не найдено"}, status=404)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=409)
    Audit.objects.create(actor=request.user.pk, action="job_" + action, target=str(job.pk))
    if request.POST.get("return") == "operations":
        return redirect("operations")
    return JsonResponse({"id": str(job.pk), "status": job.status})
