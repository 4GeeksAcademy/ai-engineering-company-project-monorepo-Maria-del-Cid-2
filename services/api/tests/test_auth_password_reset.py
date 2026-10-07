from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

os.environ["SECRET_KEY"] = "test-secret-key-for-password-reset"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from fastapi.testclient import TestClient

from app.auth.dependencies import get_password_reset_service, get_repository
from app.auth.email import EmailDeliveryError
from app.auth.models import UserCreate
from app.auth.password_reset import PasswordResetError, PasswordResetService
from app.auth.repository import PasswordResetTokenRepository, UserRepository
from app.auth.security import hash_password
from app.auth.service import AuthService
from app.main import app
from app.auth.database import create_database


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send_password_reset(
        self,
        recipient: str,
        reset_url: str,
        html_body: str | None = None,
    ) -> None:
        self.messages.append((recipient, reset_url, html_body or ""))


class FailingEmailSender:
    def send_password_reset(
        self,
        recipient: str,
        reset_url: str,
        html_body: str | None = None,
    ) -> None:
        raise EmailDeliveryError("provider unavailable")


class PasswordResetApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database = create_database(Path(self.temp_dir.name) / "auth.json")
        self.users = UserRepository(self.database)
        self.tokens = PasswordResetTokenRepository(self.database)
        self.email_sender = FakeEmailSender()
        self.service = PasswordResetService(self.users, self.tokens, self.email_sender)
        app.dependency_overrides[get_password_reset_service] = lambda: self.service
        app.dependency_overrides[get_repository] = lambda: self.users
        self.client = TestClient(app)
        payload = UserCreate(email="alice@example.com", password="oldsecret123")
        self.user = self.users.create(payload, hash_password(payload.password))

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.database.close()
        self.temp_dir.cleanup()

    def test_forgot_password_always_returns_generic_200(self) -> None:
        existing = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alice@example.com"},
        )
        missing = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "missing@example.com"},
        )

        self.assertEqual(existing.status_code, 200)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(existing.json(), missing.json())
        self.assertEqual(len(self.email_sender.messages), 1)

    def test_reset_email_contains_html_content_and_link(self) -> None:
        self.service.request_reset("alice@example.com")

        _, reset_url, html_body = self.email_sender.messages[0]
        self.assertIn(reset_url, html_body)
        self.assertIn("restablecer tu contraseña", html_body.lower())
        self.assertIn("expirará en", html_body)
        self.assertIn("no realizaste esta solicitud", html_body.lower())

    def test_forgot_password_rate_limit_allows_three_requests_per_hour(self) -> None:
        for _ in range(3):
            self.service.request_reset("alice@example.com")
        self.service.request_reset("alice@example.com")

        self.assertEqual(len(self.email_sender.messages), 3)

    def test_rate_limit_has_own_counter_per_email_and_expires_after_one_hour(self) -> None:
        current_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        service = PasswordResetService(
            self.users,
            self.tokens,
            self.email_sender,
            now=lambda: current_time,
        )
        self.users.create(
            UserCreate(email="other@example.com", password="othersecret123"),
            hash_password("othersecret123"),
        )
        for _ in range(3):
            service.request_reset("alice@example.com")
        service.request_reset("alice@example.com")
        service.request_reset("other@example.com")
        current_time += timedelta(hours=1, seconds=1)
        service.request_reset("alice@example.com")

        self.assertEqual(len(self.email_sender.messages), 5)

    def test_audit_log_records_request_and_success_without_secrets(self) -> None:
        self.service.request_reset("alice@example.com", "203.0.113.10")
        token = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]
        self.service.reset_password(token, "newsecret123", "203.0.113.10")

        events = self.database.table("password_reset_audit_log").all()
        self.assertEqual(events[0]["event_type"], "forgot_password_requested")
        self.assertEqual(events[0]["ip_address"], "203.0.113.10")
        self.assertEqual(events[1]["event_type"], "reset_password_succeeded")
        self.assertIn("timestamp", events[1])
        self.assertNotIn(token, str(events))
        self.assertNotIn("newsecret123", str(events))

    def test_forgot_password_is_generic_for_inactive_accounts_too(self) -> None:
        inactive = self.users.create(
            UserCreate(email="inactive@example.com", password="inactive123"),
            hash_password("inactive123"),
        )
        self.users._table.update({"is_active": False}, doc_ids=[inactive.id])

        existing = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alice@example.com"},
        )
        inactive_response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "inactive@example.com"},
        )
        missing = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "missing@example.com"},
        )

        self.assertEqual(
            {existing.status_code, inactive_response.status_code, missing.status_code},
            {200},
        )
        self.assertEqual(existing.json(), inactive_response.json())
        self.assertEqual(existing.json(), missing.json())
        self.assertNotIn("alice@example.com", existing.text)
        self.assertNotIn("inactive@example.com", inactive_response.text)
        self.assertNotIn("missing@example.com", missing.text)

    def test_reset_tokens_are_long_and_distinct(self) -> None:
        self.service.request_reset("alice@example.com")
        self.service.request_reset("alice@example.com")
        first = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]
        second = parse_qs(urlparse(self.email_sender.messages[1][1]).query)["token"][0]

        self.assertGreaterEqual(len(first), 40)
        self.assertNotEqual(first, second)

    def test_forgot_password_stays_generic_when_email_provider_fails(self) -> None:
        app.dependency_overrides[get_password_reset_service] = lambda: PasswordResetService(
            self.users,
            self.tokens,
            FailingEmailSender(),
        )

        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alice@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Si existe una cuenta asociada, recibirás instrucciones para restablecer la contraseña.",
        )

    def test_reset_stores_only_token_hash_and_is_one_time(self) -> None:
        token_response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alice@example.com"},
        )
        reset_url = self.email_sender.messages[0][1]
        token = reset_url.split("token=", 1)[1]

        self.assertNotIn(token, str(self.database.all()))
        response = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )
        reused = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "anothersecret123",
                "confirm_password": "anothersecret123",
            },
        )

        self.assertEqual(token_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(
            AuthService(self.users).authenticate("alice@example.com", "newsecret123").id,
            self.user.id,
        )

    def test_expired_token_is_rejected(self) -> None:
        current_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        service = PasswordResetService(
            self.users,
            self.tokens,
            self.email_sender,
            now=lambda: current_time,
        )
        service.request_reset("alice@example.com")
        token = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]
        current_time += timedelta(hours=1)

        with self.assertRaisesRegex(PasswordResetError, "Invalid or expired reset token"):
            service.reset_password(
                token,
                "newsecret123",
            )

    def test_new_reset_token_invalidates_the_previous_token(self) -> None:
        self.service.request_reset("alice@example.com")
        first_token = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]
        self.service.request_reset("alice@example.com")
        second_token = parse_qs(urlparse(self.email_sender.messages[1][1]).query)["token"][0]

        with self.assertRaisesRegex(PasswordResetError, "Invalid or expired reset token"):
            self.service.reset_password(first_token, "newsecret123")
        self.service.reset_password(second_token, "newsecret123")

    def test_concurrent_consumption_allows_only_one_reset(self) -> None:
        self.service.request_reset("alice@example.com")
        token = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]

        def consume(password: str) -> str:
            try:
                self.service.reset_password(token, password)
                return "success"
            except PasswordResetError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(consume, ["newsecret123", "anothersecret123"])
            )

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("rejected"), 1)

    def test_reset_response_does_not_expose_token_or_password(self) -> None:
        self.service.request_reset("alice@example.com")
        token = parse_qs(urlparse(self.email_sender.messages[0][1]).query)["token"][0]
        response = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(token, response.text)
        self.assertNotIn("newsecret123", response.text)

    def test_reset_invalidates_existing_jwt(self) -> None:
        old_jwt = AuthService(self.users).create_token(self.user)
        self.service.request_reset("alice@example.com")
        token = self.email_sender.messages[0][1].split("token=", 1)[1]

        self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {old_jwt}"},
        )
        self.assertEqual(response.status_code, 401)

        new_login = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "newsecret123"},
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(
            self.client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {new_login.json()['access_token']}"},
            ).status_code,
            200,
        )

    def test_change_password_requires_current_password_and_invalidates_jwt(self) -> None:
        old_jwt = AuthService(self.users).create_token(self.user)
        wrong = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "wrongsecret",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
            headers={"Authorization": f"Bearer {old_jwt}"},
        )
        self.assertEqual(wrong.status_code, 400)

        valid = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "oldsecret123",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
            headers={"Authorization": f"Bearer {old_jwt}"},
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(
            AuthService(self.users).authenticate("alice@example.com", "newsecret123").id,
            self.user.id,
        )
        self.assertEqual(
            self.client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {old_jwt}"},
            ).status_code,
            401,
        )
        self.assertNotEqual(self.users.get(self.user.id).hashed_password, "newsecret123")
        new_login = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "newsecret123"},
        )
        self.assertEqual(new_login.status_code, 200)


if __name__ == "__main__":
    unittest.main()