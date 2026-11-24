from django.urls import path

from identity import pages, views
from identity.accounts import accounts
from mice.health import health
from policy_engine.views import reevaluate

urlpatterns = [
    path("api/health", health, name="health"),
    path("", pages.login_page, name="login-page"),
    path("users/", pages.users_page, name="users-page"),
    path("logout/", pages.logout_page, name="logout-page"),
    path("api/accounts", accounts, name="accounts"),
    path("api/accounts/<str:account_id>", accounts, name="account"),
    path("api/messages/<str:message_id>/reevaluate", reevaluate, name="policy-reevaluate"),
    path("api/login", views.login_view, name="login"),
    path("api/logout", views.logout_view, name="logout"),
    path("api/me", views.me, name="me"),
    path("api/csrf", views.csrf, name="csrf"),
]
