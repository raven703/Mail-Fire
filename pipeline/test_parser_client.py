from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from pipeline.parser_client import call


class ParserBoundaryTests(SimpleTestCase):
    @override_settings(MICE_PARSER_URL="")
    def test_no_local_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "local fallback forbidden"):
            call("mail", b"input")

    @override_settings(MICE_PARSER_URL="http://parser:8090", MICE_MAX_MESSAGE_BYTES=2)
    def test_input_limit_precedes_network(self):
        with patch("pipeline.parser_client.httpx.Client") as client:
            with self.assertRaisesRegex(ValueError, "input limit"):
                call("mail", b"oversized")
            client.assert_not_called()

    def test_operation_allowlist(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            call("execute", b"input")