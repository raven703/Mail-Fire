import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


def user_id():
    return str(uuid.uuid4())


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError("Username is required")
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role="admin", is_active=True)
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.CharField(primary_key=True, max_length=36, default=user_id)
    username = models.CharField(max_length=255, unique=True)
    role = models.CharField(
        max_length=16,
        choices=[("admin", "Administrator"), ("analyst", "Analyst"), ("observer", "Observer")],
        default="observer",
    )
    originals = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    objects = UserManager()
    USERNAME_FIELD = "username"

    def has_perm(self, perm, obj=None):
        # PermissionsMixin otherwise grants every permission to superusers,
        # accidentally bypassing MICE's independent originals capability.
        from django.contrib.auth import get_backends

        return self.is_active and any(backend.has_perm(self, perm, obj) for backend in get_backends())

    class Meta:
        db_table = "mice_users"
        permissions = [
            ("access_mice", "Access MICE"),
            ("investigate", "Investigate incidents and import messages"),
            ("administer", "Administer MICE"),
            ("view_originals", "View original messages and sensitive evidence"),
        ]
