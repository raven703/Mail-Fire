"""Presentation of the latest unified analysis, without mutating stored results."""
from django.db.models.fields.json import KeyTextTransform

from pipeline.models import WorkItem


LABELS = {
    "PENDING": "Ожидает обработки", "PROCESSING": "Обрабатывается",
    "RETRYING": "Ожидает повторной попытки", "ANALYZED": "Обработано",
    "PARTIAL": "Неполный анализ", "FAILED": "Не удалось обработать",
}

REASONS = {
    "sandbox_memory_limit": "Sandbox не смог выделить память (возможно, превышен лимит)",
    "sandbox_timeout": "Превышен deadline анализа",
    "sandbox_failed": "Ошибка sandbox",
    "input_rejected": "Входные данные отклонены",
    "input_limit": "Превышен лимит входных данных",
    "queue_full": "Очередь parser заполнена",
    "busy": "Parser временно недоступен или занят",
    "ocr_unavailable": "Сервис OCR временно недоступен",
    "transport": "Нет соединения с parser",
    "timeout": "Истекло время ожидания parser",
    "wait_budget_exceeded": "Исчерпан срок ожидания сервиса",
    "WorkerDeadlineExceeded": "Превышен срок выполнения задания",
    "Cancelled": "Задание отменено",
    "AttemptsExhausted": "Исчерпаны попытки обработки",
}


def analysis_jobs():
    return WorkItem.objects.filter(kind__in=["analysis.analyze", "ingestion.parse"]).annotate(
        message_key=KeyTextTransform("message_id", "payload")
    )


def latest_jobs(messages):
    keys = [message.pk for message in messages]
    latest = {}
    if keys:
        for job in analysis_jobs().filter(message_key__in=keys).only(
            "kind", "status", "error", "attempts", "deferrals", "available_at", "created_at"
        ).order_by("-created_at", "-pk"):
            latest.setdefault(job.message_key, job)
    return latest


def describe(message, job=None):
    state = message.status
    reason = ""
    if state == "PENDING" and job:
        if job.status == "RUNNING":
            state = "PROCESSING"
        elif job.status == "PENDING" and (job.deferrals or job.attempts):
            state = "RETRYING"
        elif job.kind == "analysis.analyze" and job.status in {"DEAD", "CANCELLED"}:
            state = "FAILED"
    if state in {"RETRYING", "FAILED"} and job:
        # Only fixed diagnostic labels; never display parser bodies or secrets.
        raw = job.error or ""
        reason = next((label for token, label in REASONS.items()
                       if raw == token or ("reason=" + token) in raw.split()
                       or (token == "wait_budget_exceeded" and token in raw.split())), "")
        if "wait_budget_exceeded" in raw.split():
            reason = REASONS["wait_budget_exceeded"] + (": " + reason if reason and reason != REASONS["wait_budget_exceeded"] else "")
        if not reason:
            reason = "Ошибка обработки; подробности в журнале заданий"
    elif state == "PARTIAL":
        reason = "Часть проверок не выполнена; см. технические данные и вложения"
    elif state == "FAILED":
        reason = "Анализ не завершён"
    return {"state": state, "label": LABELS.get(state, state), "reason": reason,
            "attempts": job.attempts if job else None, "deferrals": job.deferrals if job else None,
            "next_retry": job.available_at if state == "RETRYING" and job else None,
            "previous_evidence": bool(message.content_id and state in {"PENDING", "PROCESSING", "RETRYING", "FAILED"})}


ATTACHMENT_STATES = {
    "PARTIAL": "Неполное извлечение",
    "FAILED": "Не удалось извлечь содержимое",
    "ENCRYPTED": "Вложение зашифровано",
    "UNSUPPORTED": "Формат не поддерживается",
}


def attachment_reason(attachment):
    details = attachment.details if isinstance(attachment.details, dict) else {}
    error = details.get("error")
    fixed = {"page limit": "Превышен лимит страниц", "archive depth": "Превышена глубина архивов",
             "MemoryError": "Не удалось выделить память", "OCRRejected": "OCR отклонил вложение"}
    if isinstance(error, str) and error in fixed:
        return fixed[error]
    if details.get("ocr_required"):
        return "Для извлечения текста требуется OCR"
    return ATTACHMENT_STATES.get(attachment.status, "")
