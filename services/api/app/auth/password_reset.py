"""Password reset orchestration independent from the HTTP layer."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from .config import PASSWORD_RESET_FRONTEND_URL, PASSWORD_RESET_TOKEN_EXPIRE_DELTA
from .email import EmailSender
from .repository import PasswordResetTokenRepository, UserRepository
from .security import (
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)


class PasswordResetError(Exception):
    """Expected reset failure that should have a generic public message."""


class PasswordResetService:
    def __init__(
        self,
        users: UserRepository,
        tokens: PasswordResetTokenRepository,
        email_sender: EmailSender,
        *,
        now: callable = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._email_sender = email_sender
        self._now = now

    def request_reset(self, email: str) -> None:
        user = self._users.get_by_email(email.strip())
        if user is None or not user.is_active:
            return

        now = self._now()
        raw_token = create_password_reset_token()
        self._tokens.replace_for_user(
            user.id,
            hash_password_reset_token(raw_token),
            now,
            now + PASSWORD_RESET_TOKEN_EXPIRE_DELTA,
        )
        reset_url = f"{PASSWORD_RESET_FRONTEND_URL}?token={quote(raw_token)}"
        self._email_sender.send_password_reset(user.email, reset_url)

    def reset_password(self, token: str, new_password: str) -> None:
        reset_token = self._tokens.get_by_hash(hash_password_reset_token(token))
        now = self._now()
        if (
            reset_token is None
            or reset_token.used_at is not None
            or reset_token.expires_at <= now
        ):
            raise PasswordResetError("Invalid or expired reset token")

        user = self._users.get(reset_token.user_id)
        if user is None or not user.is_active:
            raise PasswordResetError("Invalid or expired reset token")

        hashed_password = hash_password(new_password)
        if not self._tokens.consume(reset_token.id, now):
            raise PasswordResetError("Invalid or expired reset token")
        self._users.update_password(user.id, hashed_password)

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        user = self._users.get(user_id)
        if user is None or not verify_password(current_password, user.hashed_password):
            raise PasswordResetError("Current password is incorrect")
        if self._users.update_password(user_id, hash_password(new_password)) is None:
            raise PasswordResetError("Current password is incorrect")