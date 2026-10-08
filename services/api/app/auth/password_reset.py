"""Password reset orchestration independent from the HTTP layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .config import PASSWORD_RESET_FRONTEND_URL, PASSWORD_RESET_TOKEN_EXPIRE_DELTA
from .email import EmailSender, build_password_reset_html
from .repository import (
    PasswordResetAuditLogRepository,
    PasswordResetRateLimitRepository,
    PasswordResetTokenRepository,
    UserRepository,
)
from .security import (
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)


class PasswordResetError(Exception):
    """Expected reset failure that should have a generic public message."""


PASSWORD_RESET_REQUEST_LIMIT = 5
PASSWORD_RESET_RATE_LIMIT_WINDOW = timedelta(hours=0)


class PasswordResetService:
    def __init__(
        self,
        users: UserRepository,
        tokens: PasswordResetTokenRepository,
        email_sender: EmailSender,
        *,
        now: callable = lambda: datetime.now(timezone.utc),
        rate_limits: PasswordResetRateLimitRepository | None = None,
        audit_log: PasswordResetAuditLogRepository | None = None,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._email_sender = email_sender
        self._now = now
        database = users._db
        self._rate_limits = rate_limits or PasswordResetRateLimitRepository(database)
        self._audit_log = audit_log or PasswordResetAuditLogRepository(database)

    def request_reset(self, email: str, ip_address: str | None = None) -> None:
        normalized_email = email.strip().lower()
        now = self._now()
        self._audit_log.record(
            "forgot_password_requested",
            now,
            ip_address,
            normalized_email,
        )
        allowed = self._rate_limits.allow(
            normalized_email,
            now,
            PASSWORD_RESET_REQUEST_LIMIT,
            PASSWORD_RESET_RATE_LIMIT_WINDOW,
        )
        if not allowed:
            return

        user = self._users.get_by_email(normalized_email)
        if user is None or not user.is_active:
            return

        raw_token = create_password_reset_token()
        self._tokens.replace_for_user(
            user.id,
            hash_password_reset_token(raw_token),
            now,
            now + PASSWORD_RESET_TOKEN_EXPIRE_DELTA,
        )
        reset_url = f"{PASSWORD_RESET_FRONTEND_URL}?token={quote(raw_token)}"
        self._email_sender.send_password_reset(
            user.email,
            reset_url,
            build_password_reset_html(reset_url),
        )

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: str | None = None,
    ) -> None:
        reset_token = self._tokens.get_by_hash(hash_password_reset_token(token))
        now = self._now()
        if (
            reset_token is None
            or reset_token.used_at is not None
            or reset_token.expires_at <= now
        ):
            self._audit_log.record("reset_password_failed", now, ip_address)
            raise PasswordResetError("Invalid or expired reset token")

        user = self._users.get(reset_token.user_id)
        if user is None or not user.is_active:
            self._audit_log.record("reset_password_failed", now, ip_address)
            raise PasswordResetError("Invalid or expired reset token")

        hashed_password = hash_password(new_password)
        if not self._tokens.consume(reset_token.id, now):
            self._audit_log.record("reset_password_failed", now, ip_address, user.email)
            raise PasswordResetError("Invalid or expired reset token")
        self._users.update_password(user.id, hashed_password)
        self._audit_log.record("reset_password_succeeded", now, ip_address, user.email)

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