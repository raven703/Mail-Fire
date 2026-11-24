import json

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST

from records.models import Audit


def identity_response(user):
    return {"username": user.username, "role": user.role, "originals": user.originals}


@require_GET
def csrf(request):
    return JsonResponse({"csrf": get_token(request)})


@require_POST
def login_view(request):
    try:
        body = json.loads(request.body)
        username, password = body["username"], body["password"]
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError()
        if len(username) > 128 or len(password) > 1024:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"detail": "Некорректные данные"}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Неверные учётные данные"}, status=401)
    with transaction.atomic():
        login(request, user)
        Audit.objects.create(actor=user.pk, action="login", target=user.pk)
    return JsonResponse({**identity_response(user), "csrf": get_token(request)})


@require_GET
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    return JsonResponse(identity_response(request.user))


@require_POST
def logout_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    logout(request)
    return JsonResponse({"ok": True})
