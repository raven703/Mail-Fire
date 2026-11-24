from argon2 import PasswordHasher
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.test import Client, TestCase

from identity.accounts import AccountError, save_account
from identity.models import User
from records.models import Account


class AuthCutoverTests(TestCase):
    def test_account_management_sync_revocation_and_self_protection(self):
        admin = User.objects.create_user("administrator", "admin-test-password", role="admin")
        self.assertTrue(Account.objects.filter(pk=admin.pk, role="admin").exists())
        user = save_account(
            admin,
            {
                "username": "new-analyst",
                "role": "analyst",
                "originals": True,
                "password": "analyst-test-password",
            },
        )
        self.assertEqual(Account.objects.get(pk=user.pk).username, user.username)
        self.client.post(
            "/api/login",
            {"username": user.username, "password": "analyst-test-password"},
            content_type="application/json",
        )
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        save_account(admin, {"username": user.username, "role": "observer"}, user.pk)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        with self.assertRaises(AccountError):
            save_account(admin, account_id=admin.pk, revoke=True)
        save_account(admin, account_id=user.pk, revoke=True)
        self.assertFalse(Account.objects.get(pk=user.pk).enabled)

    def test_import_login_upgrade_and_permissions(self):
        account = Account.objects.create(
            username="legacy-admin",
            password_hash=PasswordHasher().hash("a-test-password"),
            role="admin",
            originals=False,
            enabled=True,
        )
        call_command("import_legacy_accounts", verbosity=0)
        user = authenticate(username="legacy-admin", password="a-test-password")
        self.assertEqual(user.pk, account.pk)
        self.assertTrue(user.password.startswith("argon2$"))
        self.assertTrue(user.has_perm("identity.administer"))
        self.assertFalse(user.has_perm("identity.view_originals"))
        user.is_superuser = True
        self.assertFalse(user.has_perm("identity.view_originals"))
        user.role = "observer"
        self.assertFalse(user.has_perm("identity.investigate"))
        user.is_active = False
        self.assertFalse(user.has_perm("identity.access_mice"))
        call_command("import_legacy_accounts", verbosity=0)
        self.assertEqual(User.objects.count(), 1)

    def test_csrf_login_logout_and_disabled_account(self):
        user = User.objects.create_user("analyst", "test-password", role="analyst")
        client = Client(enforce_csrf_checks=True)
        body = {"username": "analyst", "password": "test-password"}
        self.assertEqual(client.post("/api/login", body, content_type="application/json").status_code, 403)
        token = client.get("/api/csrf").json()["csrf"]
        response = client.post("/api/login", body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/me").json()["role"], "analyst")
        self.assertEqual(
            client.post("/api/logout", HTTP_X_CSRFTOKEN=response.json()["csrf"]).status_code, 200
        )
        self.assertEqual(client.get("/api/me").status_code, 401)
        user.is_active = False
        user.save()
        self.assertIsNone(authenticate(username="analyst", password="test-password"))
