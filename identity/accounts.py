import json
import re

from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from identity.models import User
from records.models import Audit, LoginSession


class AccountError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def public(user):
    return {
        "id": user.pk,
        "username": user.username,
        "role": user.role,
        "originals": user.originals,
        "enabled": user.is_active,
    }


def validate(body, creating=False):
    if not isinstance(body, dict):
        raise AccountError("Некорректные данные", 422)
    username, role = body.get("username"), body.get("role")
    if (
        not isinstance(username, str)
        or not 3 <= len(username) <= 100
        or not re.fullmatch(r"[\w.@+-]+", username)
    ):
        raise AccountError("Некорректное имя пользователя", 422)
    if role not in {"admin", "analyst", "observer"}:
        raise AccountError("Некорректная роль", 422)
    for field in ("enabled", "originals"):
        if field in body and type(body[field]) is not bool:
            raise AccountError("Некорректное значение " + field, 422)
    password = body.get("password")
    if password is not None and (not isinstance(password, str) or not 12 <= len(password) <= 128):
        raise AccountError("Пароль должен содержать от 12 до 128 символов", 422)
    if creating and password is None:
        raise AccountError("Укажите пароль", 422)
    return {
        "username": username,
        "role": role,
        "is_active": body.get("enabled", True),
        "originals": body.get("originals", False),
        "password": password,
    }


@transaction.atomic
def save_account(actor, body=None, account_id=None, revoke=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('accounts-admin'))")
    # Recheck the actor under the same lock as concurrent role changes.
    actor = User.objects.get(pk=actor.pk)
    if not actor.is_active or actor.role != "admin":
        raise AccountError("Недостаточно прав", 403)
    row = User.objects.select_for_update().filter(pk=account_id).first() if account_id else None
    if account_id and row is None:
        raise AccountError("Пользователь не найден", 404)
    if revoke:
        if row.pk == actor.pk:
            raise AccountError("Нельзя удалить собственную учётную запись")
        values = {"is_active": False, "role": row.role}
    else:
        values = validate(body, creating=row is None)
        if User.objects.filter(username=values["username"]).exclude(pk=account_id).exists():
            raise AccountError("Имя уже используется")
    losing_admin = not values["is_active"] or values["role"] != "admin"
    if row and row.pk == actor.pk and losing_admin:
        raise AccountError("Нельзя отключить собственный административный доступ")
    if row and row.is_active and row.role == "admin" and losing_admin:
        if not User.objects.filter(is_active=True, role="admin").exclude(pk=row.pk).exists():
            raise AccountError("Нельзя отключить последнего администратора")
    row = row or User()
    if revoke:
        row.is_active = False
    else:
        password = values.pop("password")
        for name, value in values.items():
            setattr(row, name, value)
        row.is_staff = row.role == "admin"
        if password is not None:
            row.set_password(password)
    row.access_version += 1
    row.save()
    LoginSession.objects.filter(account_id=row.pk).delete()
    Audit.objects.create(
        actor=actor.pk,
        action="account_revoke" if revoke else "account_update",
        target=row.pk,
        details={} if revoke else public(row),
    )
    return row


@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def accounts(request, account_id=None):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    if not request.user.has_perm("identity.administer"):
        return JsonResponse({"detail": "Требуется администратор"}, status=403)
    if request.method == "GET" and account_id is None:
        return JsonResponse({"items": [public(user) for user in User.objects.order_by("username")]})
    if (
        (request.method == "POST" and account_id is not None)
        or (request.method in {"PUT", "DELETE"} and account_id is None)
        or request.method == "GET"
    ):
        return JsonResponse({"detail": "Метод не поддерживается"}, status=405)
    try:
        body = json.loads(request.body) if request.method != "DELETE" else None
        row = save_account(request.user, body, account_id, revoke=request.method == "DELETE")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Некорректный JSON"}, status=400)
    except AccountError as exc:
        return JsonResponse({"detail": str(exc)}, status=exc.status)
    return JsonResponse({"deleted": True, "deactivated": True} if request.method == "DELETE" else public(row))
