import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from policy_engine.service import EvidenceUnavailable, request_evaluation
from records.models import Message


@require_POST
def reevaluate(request, message_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    if not request.user.has_perm("identity.investigate"):
        return JsonResponse({"detail": "Недостаточно прав"}, status=403)
    try:
        body = json.loads(request.body or b"{}")
        request_id = str(uuid.UUID(body.get("request_id", str(uuid.uuid4()))))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Некорректный request_id"}, status=400)
    try:
        job = request_evaluation(message_id, request_id)
    except Message.DoesNotExist:
        return JsonResponse({"detail": "Письмо не найдено"}, status=404)
    except EvidenceUnavailable as exc:
        return JsonResponse({"detail": str(exc), "requires_analysis": True}, status=409)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=409)
    return JsonResponse({"job_id": str(job.pk), "status": job.status, "request_id": request_id}, status=202)
