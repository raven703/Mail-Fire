from django.test import SimpleTestCase, TestCase, override_settings

from identity.models import User
from records.models import Setting
from records.performance import PerformanceForm


VALUES = {
    "MICE_UNIFIED_ANALYSIS_ENABLED": "on", "MICE_ANALYSIS_CONCURRENCY": "2",
    "MICE_PARSER_CONCURRENCY": "2", "MICE_SANDBOX_ADDRESS_LIMIT_MIB": "1024",
}


class PerformanceFormTests(SimpleTestCase):
    def test_valid_and_unsafe_configuration(self):
        self.assertTrue(PerformanceForm(VALUES).is_valid())
        self.assertFalse(PerformanceForm({**VALUES, "MICE_PARSER_CONCURRENCY": "3"}).is_valid())
        self.assertFalse(PerformanceForm({**VALUES, "MICE_ANALYSIS_CONCURRENCY": "3"}).is_valid())


class PerformancePageTests(TestCase):
    @override_settings(MICE_UNIFIED_ANALYSIS_ENABLED=False)
    def test_save_and_export_are_not_hot_application(self):
        user = User.objects.create_superuser("performance-admin", "test-password-long")
        self.client.force_login(user)
        session = self.client.session
        session["mice_access_version"] = user.access_version
        session.save()
        self.assertContains(self.client.get("/settings/performance/"), "Производительность")
        self.assertEqual(self.client.post("/settings/performance/", VALUES).status_code, 302)
        self.assertTrue(Setting.objects.get(pk="performance_deployment").value["MICE_UNIFIED_ANALYSIS_ENABLED"])
        response = self.client.get("/settings/performance/?download=env")
        self.assertContains(response, "MICE_UNIFIED_ANALYSIS_ENABLED=true")
        self.assertContains(response, "MICE_ANALYSIS_CONCURRENCY=2")
        self.assertContains(self.client.get("/settings/performance/"), "Требуется применение администратором")
