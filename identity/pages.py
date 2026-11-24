from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from identity.accounts import AccountError, save_account
from identity.models import User
from records.models import Audit, Setting


@require_http_methods(["GET", "POST"])
def login_page(request):
    if request.user.is_authenticated:
        return redirect("overview-page")
    error = ""
    if request.method == "POST":
        username, password = request.POST.get("username", ""), request.POST.get("password", "")
        user = (
            authenticate(request, username=username, password=password)
            if len(username) <= 128 and len(password) <= 1024
            else None
        )
        if user:
            login(request, user)
            request.session["mice_access_version"] = user.access_version
            Audit.objects.create(actor=user.pk, action="login", target=user.pk)
            return redirect("overview-page")
        error = "Неверные учётные данные"
    return render(request, "identity/login.html", {"error": error})


@require_POST
def logout_page(request):
    logout(request)
    return redirect("login-page")


@require_http_methods(["GET", "POST"])
def users_page(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    if not request.user.has_perm("identity.administer"):
        return render(request, "identity/access.html", status=403)
    error, editing = "", None
    if request.method == "POST":
        identifier = request.POST.get("id") or None
        body = {
            "username": request.POST.get("username", ""),
            "role": request.POST.get("role", ""),
            "enabled": "enabled" in request.POST,
            "originals": "originals" in request.POST,
        }
        if request.POST.get("password"):
            body["password"] = request.POST["password"]
        try:
            save_account(request.user, body, identifier, revoke=request.POST.get("action") == "revoke")
            return redirect("users-page")
        except AccountError as exc:
            error = str(exc)
            editing = {**body, "id": identifier}
    elif request.GET.get("edit"):
        row = User.objects.filter(pk=request.GET["edit"]).first()
        if row:
            editing = {
                "id": row.pk,
                "username": row.username,
                "role": row.role,
                "enabled": row.is_active,
                "originals": row.originals,
            }
    elif request.GET.get("new"):
        editing = {"role": "analyst", "enabled": True, "originals": True}
    return render(
        request,
        "identity/users.html",
        {
            "users": User.objects.order_by("username"),
            "editing": editing,
            "show_editor": editing is not None,
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def preferences(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход"}, status=401)
    key = "ui:" + request.user.pk
    if request.method == "POST":
        theme = request.POST.get("theme")
        if theme not in {"light", "dark", "system"}:
            return JsonResponse({"detail": "Неизвестная тема"}, status=400)
        Setting.objects.update_or_create(pk=key, defaults={"value": {"theme": theme}})
    else:
        row = Setting.objects.filter(pk=key).first()
        theme = row.value.get("theme", "system") if row else "system"
    return JsonResponse({"theme": theme})
