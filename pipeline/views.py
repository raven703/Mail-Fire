from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from pipeline.models import WorkItem
from pipeline.monitoring import database_snapshot, flow_snapshot, flow_summary, snapshot, stage_snapshot
from pipeline.resource_history import service_series
from pipeline.services import cancel, retry
from records.models import Audit, Diagnostic

TABS = (
    ("queues", "Очереди"), ("flow", "Почтовый поток"), ("resources", "История ресурсов"),
    ("database", "PostgreSQL"), ("jobs", "Задания"),
)


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
    status, queue = request.GET.get("status", ""), request.GET.get("queue", "")
    tab = request.GET.get("tab", "jobs" if status or queue else "queues")
    if tab not in dict(TABS):
        tab = "queues"
    admin = request.user.has_perm("identity.administer")
    context = {"tab": tab, "tabs": TABS, "can_administer": admin}
    if tab == "queues":
        context.update(monitor=snapshot(), stages=stage_snapshot())
    elif tab == "flow":
        context.update(flow=flow_snapshot(), flow_summary=flow_summary())
    elif tab == "resources":
        context["resource_history"] = service_series()
    elif tab == "database" and admin:
        context["database"] = database_snapshot()
    elif tab == "jobs":
        jobs = WorkItem.objects.order_by("-created_at")
        if status == "active":
            jobs = jobs.filter(status__in=[WorkItem.Status.PENDING, WorkItem.Status.RUNNING])
        elif status:
            jobs = jobs.filter(status=status)
        if queue:
            jobs = jobs.filter(queue=queue)
        context.update(jobs=jobs[:100], diagnostics=Diagnostic.objects.order_by("-created_at").values(
            "created_at", "service", "level", "event",
        )[:30])
    return render(request, "pipeline/operations.html", context)


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
        response = redirect("operations")
        response["Location"] += "?tab=jobs"
        return response
    return JsonResponse({"id": str(job.pk), "status": job.status})
