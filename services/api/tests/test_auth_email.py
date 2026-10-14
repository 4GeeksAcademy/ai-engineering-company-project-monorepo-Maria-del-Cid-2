from __future__ import annotations

import os
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

os.environ["SECRET_KEY"] = "test-secret-key-for-email-tests"

from app.auth.email import EmailDeliveryError, ResendEmailSender


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class EmailLoggingTests(unittest.TestCase):
    def test_provider_http_error_logs_status_without_recipient_or_body(self) -> None:
        body = b"secret-provider-response-body"
        error = HTTPError(
            "https://api.resend.com/emails",
            422,
            "invalid request",
            hdrs=None,
            fp=mock.Mock(read=mock.Mock(return_value=body)),
        )
        sender = ResendEmailSender(api_key="test-api-key")

        with mock.patch("app.auth.email.urlopen", side_effect=error):
            with self.assertLogs("app.auth.email", level="WARNING") as logs:
                with self.assertRaises(EmailDeliveryError):
                    sender.send_password_reset(
                        "sensitive-recipient@example.com",
                        "https://frontend.test/reset?token=secret-token",
                    )

        output = "\n".join(logs.output)
        self.assertIn("status=422", output)
        self.assertIn("HTTPError", output)
        self.assertNotIn("sensitive-recipient@example.com", output)
        self.assertNotIn("secret-provider-response-body", output)
        self.assertNotIn("secret-token", output)

    def test_provider_connection_error_logs_type_without_error_details(self) -> None:
        sender = ResendEmailSender(api_key="test-api-key")

        with mock.patch(
            "app.auth.email.urlopen",
            side_effect=URLError("sensitive-network-detail"),
        ):
            with self.assertLogs("app.auth.email", level="WARNING") as logs:
                with self.assertRaises(EmailDeliveryError):
                    sender.send_password_reset(
                        "sensitive-recipient@example.com",
                        "https://frontend.test/reset?token=secret-token",
                    )

        output = "\n".join(logs.output)
        self.assertIn("URLError", output)
        self.assertNotIn("sensitive-recipient@example.com", output)
        self.assertNotIn("sensitive-network-detail", output)
        self.assertNotIn("secret-token", output)

    def test_success_log_contains_only_recipient_domain_and_status(self) -> None:
        sender = ResendEmailSender(api_key="test-api-key")

        with mock.patch("app.auth.email.urlopen", return_value=_Response(202)):
            with self.assertLogs("app.auth.email", level="INFO") as logs:
                sender.send_password_reset(
                    "sensitive-recipient@example.com",
                    "https://frontend.test/reset?token=secret-token",
                )

        output = "\n".join(logs.output)
        self.assertIn("recipient_domain=example.com", output)
        self.assertIn("status=202", output)
        self.assertNotIn("sensitive-recipient@example.com", output)
        self.assertNotIn("secret-token", output)
    def test_provider_rejection_response_raises_error(self) -> None:
        """Respuesta HTTP no-2xx del provider levanta EmailDeliveryError."""
        sender = ResendEmailSender(api_key="test-api-key")

        with mock.patch("app.auth.email.urlopen", return_value=_Response(422)):
            with self.assertLogs("app.auth.email", level="WARNING") as logs:
                with self.assertRaises(EmailDeliveryError):
                    sender.send_password_reset(
                        "sensitive-recipient@example.com",
                        "https://frontend.test/reset?token=secret-token",
                    )

        output = "\n".join(logs.output)
        self.assertIn("status=422", output)
        self.assertNotIn("sensitive-recipient@example.com", output)
        self.assertNotIn("secret-token", output)

    def test_provider_timeout_raises_error(self) -> None:
        """TimeoutError del provider levanta EmailDeliveryError."""
        sender = ResendEmailSender(api_key="test-api-key")

        with mock.patch(
            "app.auth.email.urlopen",
            side_effect=TimeoutError("connection timed out"),
        ):
            with self.assertLogs("app.auth.email", level="WARNING") as logs:
                with self.assertRaises(EmailDeliveryError):
                    sender.send_password_reset(
                        "sensitive-recipient@example.com",
                        "https://frontend.test/reset?token=secret-token",
                    )

        output = "\n".join(logs.output)
        self.assertIn("TimeoutError", output)
        self.assertNotIn("sensitive-recipient@example.com", output)
        self.assertNotIn("secret-token", output)

    def test_provider_no_api_key_raises_error(self) -> None:
        """Sin API key → EmailDeliveryError sin llamar a urlopen."""
        sender = ResendEmailSender(api_key="")

        with self.assertRaisesRegex(
            EmailDeliveryError, "Email provider is not configured"
        ):
            sender.send_password_reset(
                "recipient@example.com",
                "https://frontend.test/reset?token=secret-token",
            )

if __name__ == "__main__":
    unittest.main()