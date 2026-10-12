"""Email delivery boundary for authentication messages."""

from __future__ import annotations

import json
import logging
from html import escape
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import (
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    RESEND_API_KEY,
    RESEND_FROM_EMAIL,
)

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when the configured email provider cannot deliver a message."""


def _recipient_context(recipient: str) -> str:
    """Return non-sensitive recipient context for diagnostics."""
    _, separator, domain = recipient.partition("@")
    return domain if separator and domain else "invalid-recipient"


class EmailSender(Protocol):
    def send_password_reset(
        self,
        recipient: str,
        reset_url: str,
        html_body: str | None = None,
    ) -> None:
        """Send a password reset message without exposing implementation details."""


def build_password_reset_html(reset_url: str) -> str:
        """Build the small HTML body used by password reset emails."""
        safe_url = escape(reset_url, quote=True)
        return f"""\
<html>
    <body style="font-family:Arial,sans-serif;color:#25313c;line-height:1.5">
        <h1 style="color:#e87525">Restablece tu contraseña de Nexova</h1>
        <p>Hemos recibido una solicitud para restablecer tu contraseña.</p>
        <p><a href="{safe_url}" style="color:#e87525;font-weight:bold">Restablecer contraseña</a></p>
        <p>Este enlace expirará en {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos.</p>
        <p>Si no realizaste esta solicitud, puedes ignorar este mensaje.</p>
    </body>
</html>"""


class ResendEmailSender:
    """Small Resend adapter using the provider HTTP API."""

    def __init__(
        self,
        api_key: str = RESEND_API_KEY,
        from_email: str = RESEND_FROM_EMAIL,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send_password_reset(
        self,
        recipient: str,
        reset_url: str,
        html_body: str | None = None,
    ) -> None:
        if not self._api_key:
            raise EmailDeliveryError("Email provider is not configured")

        html = html_body or build_password_reset_html(reset_url)
        payload = json.dumps(
            {
                "from": self._from_email,
                "to": [recipient],
                "subject": "Restablece tu contraseña de Nexova",
                "text": (
                    "Solicitaste restablecer tu contraseña de Nexova. "
                    f"Usa este enlace temporal: {reset_url}. "
                    f"Caduca en {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos."
                ),
                "html": html,
            }
        ).encode("utf-8")
        request = Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                #
                #
                "User-Agent": "nexova-api/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status < 200 or response.status >= 300:
                    logger.warning(
                        "password-reset email provider rejected message "
                        "provider=resend recipient_domain=%s status=%s",
                        _recipient_context(recipient),
                        response.status,
                    )
                    raise EmailDeliveryError("Email provider rejected the message")
                logger.info(
                    "password-reset email accepted by provider "
                    "provider=resend recipient_domain=%s status=%s",
                    _recipient_context(recipient),
                    response.status,
                )
        except HTTPError as exc:
            logger.warning(
                "password-reset email provider rejected message "
                "provider=resend recipient_domain=%s status=%s failure_type=%s",
                _recipient_context(recipient),
                exc.code,
                type(exc).__name__,
            )
            raise EmailDeliveryError("Email provider rejected the message") from exc
        except (URLError, TimeoutError) as exc:
            logger.warning(
                "password-reset email provider unavailable "
                "provider=resend recipient_domain=%s failure_type=%s",
                _recipient_context(recipient),
                type(exc).__name__,
            )
            raise EmailDeliveryError("Email provider is unavailable") from exc