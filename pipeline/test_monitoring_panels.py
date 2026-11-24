from unittest.mock import MagicMock, patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from pipeline.monitoring import service_snapshot, stage_snapshot


class MonitoringPanelTests(SimpleTestCase):
    @override_settings(MICE_PARSER_URL="http://parser", MICE_OCR_PARSER_URL="", MICE_CONVERTER_URL="http://converter")
    def test_fixed_services_and_unconfigured_state(self):
        with patch("pipeline.monitoring.httpx.Client") as client:
            client.return_value.__enter__.return_value.get.return_value.status_code = 200
            rows = service_snapshot()
        self.assertEqual([row["state"] for row in rows], ["available", "not configured", "available"])
        self.assertEqual(rows[-1]["name"], "Converter")

    def test_stage_percentiles_and_rendering(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("parse", "DONE", 3, 2, 4.5, 7.2, None, 0)]
        with patch("pipeline.monitoring.connection") as connect:
            connect.cursor.return_value.__enter__.return_value = cursor
            rows = stage_snapshot()
        self.assertEqual(rows[0]["p95_seconds"], 7.2)
        self.assertIn("percentile_cont(.95)", cursor.execute.call_args.args[0])
        html = render_to_string("pipeline/_stages.html", {"stages": rows})
        self.assertIn("parse", html)
        self.assertIn("p95", html)

    def test_workspace_templates_compile(self):
        from django.template.loader import get_template

        for name in ("identity/base.html", "pipeline/operations.html", "records/messages.html",
                     "records/incidents.html", "records/_selection_filters.html", "records/_investigation_filters.html"):
            with self.subTest(template=name):
                get_template(name)