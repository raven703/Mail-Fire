from django.urls import path

from identity import views

urlpatterns = [
    path("api/login", views.login_view, name="login"),
    path("api/logout", views.logout_view, name="logout"),
    path("api/me", views.me, name="me"),
    path("api/csrf", views.csrf, name="csrf"),
]
