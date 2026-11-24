from django.urls import path

from identity import pages, views
from identity.accounts import accounts
from mice.health import health
from pipeline import views as pipeline_views
from pipeline.uploads import upload_message
from policy_engine.catalog_views import policies
from policy_engine.category_pages import categories
from policy_engine.pages import catalog
from policy_engine.rulepacks import page as rulepacks_page
from policy_engine.views import reevaluate
from records import workspace
from records.attachments import attachment
from records.catalogs import catalog as identity_catalog
from records.datasets import datasets
from records.llm_configuration import configuration as llm_page
from records.messages import imports, messages, overview
from records.model_management import models as models_page
from records.operations import audit, configuration
from records.references import references
from records.retention import legal_hold, retention
from records.semantic import page as semantic_page

urlpatterns = [
    path("semantic/", semantic_page, name="semantic-page"),
    path("models/", models_page, name="models-page"),
    path("llm/", llm_page, name="llm-page"),
    path("rulepacks/", rulepacks_page, name="rulepacks-page"),
    path("overview/", overview, name="overview-page"),
    path("messages/", messages, name="messages-page"),
    path("imports/", imports, name="imports-page"),
    path("retention/", retention, name="retention-page"),
    path("messages/<str:message_id>/hold/", legal_hold, name="message-hold"),
    path("employees/", identity_catalog, {"kind": "employees"}, name="employees-page"),
    path("employees/<str:object_id>/", identity_catalog, {"kind": "employees"}, name="employee-edit"),
    path("addresses/", identity_catalog, {"kind": "addresses"}, name="addresses-page"),
    path("addresses/<str:object_id>/", identity_catalog, {"kind": "addresses"}, name="address-edit"),
    path("references/", references, name="references-page"),
    path("attachments/<str:attachment_id>/", attachment, name="attachment-detail"),
    path("attachments/<str:attachment_id>/page/", attachment, {"action": "page"}, name="attachment-page"),
    path("attachments/<str:attachment_id>/download/", attachment, {"action": "download"}, name="attachment-download"),
    path("settings/", configuration, name="configuration-page"),
    path("audit/", audit, name="audit-page"),
    path("datasets/", datasets, name="datasets-page"),
    path("datasets/<str:dataset_id>/", datasets, name="dataset-detail"),
    path("categories/", categories, name="categories-page"),
    path("categories/<str:category_id>/", categories, name="category-detail"),
    path("categories/<str:category_id>/rules/<str:rule_id>/", categories, name="category-rule"),
    path("incidents/", workspace.incidents, name="incidents-page"),
    path("incidents/<str:incident_id>/", workspace.incident_detail, name="incident-detail"),
    path("messages/<str:message_id>/original/", workspace.original_message, name="message-original"),
    path("messages/upload/", upload_message, name="message-upload"),
    path("messages/<str:message_id>/", workspace.message_detail, name="message-detail"),
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
