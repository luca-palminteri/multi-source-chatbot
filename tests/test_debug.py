from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.debug import failure_details, log_failure, stage
from assistant.chat import render_turn


class DebugTests(unittest.TestCase):
    def test_failure_omits_secret_exception_message(self):
        class ProviderError(Exception):
            code = 429
        try:
            raise ProviderError("API_KEY=secret-key; prompt=private")
        except ProviderError as exc:
            self.assertEqual(failure_details(exc), {"error_type": "ProviderError", "status_code": 429})
            with self.assertLogs("assistant.debug", level="DEBUG") as logs:
                log_failure("Gemini", exc)
        output = "\n".join(logs.output)
        self.assertIn("429", output)
        self.assertNotIn("secret-key", output)
        self.assertNotIn("private", output)

    def test_wrapped_google_error_exposes_status_and_retry_without_message(self):
        cause = Exception("secret credential")
        cause.code = 429
        cause.details = {"error": {"message": "secret", "details": [
            {"retryDelay": "12.5s"},
            {"violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_content_requests"}]}]}}
        error = RuntimeError("private provider message")
        error.__cause__ = cause
        details = failure_details(error)
        self.assertEqual(details["status_code"], 429)
        self.assertEqual(details["retry_after_seconds"], 12.5)
        self.assertNotIn("secret", str(details))
        self.assertNotIn("private", str(details))

    def test_stage_preserves_failure_and_reports_timing(self):
        with self.assertLogs("assistant.debug", level="DEBUG") as logs:
            with self.assertRaises(ConnectionError):
                with stage("Query embedding"):
                    raise ConnectionError("secret")
        self.assertIn("Query embedding started", "\n".join(logs.output))
        self.assertIn("finished after", "\n".join(logs.output))

    def test_terminal_displays_failure_type_and_status(self):
        output = []
        render_turn({"answer": "Stopped", "trace": [{"event": "execution_failed",
                    "error_type": "ProviderError", "status_code": 429}]}, output.append)
        self.assertIn("Failure type: ProviderError; HTTP status: 429", output)
