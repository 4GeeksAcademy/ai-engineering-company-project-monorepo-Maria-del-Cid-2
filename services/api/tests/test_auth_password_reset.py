from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["SECRET_KEY"] = "test-secret-key-for-password-reset"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from fastapi.testclient import TestClient

from app.auth.dependencies import get_password_reset_service, get_repository
from app.auth.email import EmailDeliveryError
from app.auth.models import UserCreate
from app.auth.password_reset import PasswordResetService
from app.auth.repository import PasswordResetTokenRepository, UserRepository
from app.auth.security import hash_password
from app.auth.service import AuthService
from app.main import app
from app.auth.database import create_database


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        self.messages.append((recipient, reset_url))


class FailingEmailSender:
    def send_password_reset(self, recipient: str, reset_url: str) -> None:
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


if __name__ == "__main__":
    unittest.main()