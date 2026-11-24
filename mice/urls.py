from django.urls import path

from identity import pages, views
from identity.accounts import accounts
from mice.health import health
from pipeline import views as pipeline_views
from pipeline.uploads import upload_message
from policy_engine.catalog_views import policies
from policy_engine.pages import catalog
from policy_engine.views import reevaluate

urlpatterns = [
    path("messages/upload/", upload_message, name="message-upload"),
    path("policies/", catalog, name="policies-page"),
    path("api/catalog/policies", policies, name="policy-list"),
    path("api/workspace/policies", policies, name="policy-create"),
    path("api/workspace/policies/<str:policy_id>", policies, name="policy-update"),
    path("api/workspace/policies/<str:policy_id>/<str:action>", policies, name="policy-action"),
    path(
        "api/catalog/policies/<str:policy_id>/enabled", policies, {"action": "enabled"}, name="policy-toggle"
    ),
    path("operations/", pipeline_views.operations, name="operations"),
    path("api/monitor/queues", pipeline_views.monitor_api, name="queue-monitor"),
    path("api/jobs/<uuid:job_id>/<str:action>", pipeline_views.control, name="job-control"),
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
