"""Email delivery boundary for authentication messages."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import RESEND_API_KEY, RESEND_FROM_EMAIL


class EmailDeliveryError(Exception):
    """Raised when the configured email provider cannot deliver a message."""


class EmailSender(Protocol):
    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        """Send a password reset message without exposing implementation details."""


class ResendEmailSender:
    """Small Resend adapter using the provider HTTP API."""

    def __init__(
        self,
        api_key: str = RESEND_API_KEY,
        from_email: str = RESEND_FROM_EMAIL,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        if not self._api_key:
            raise EmailDeliveryError("Email provider is not configured")

        payload = json.dumps(
            {
                "from": self._from_email,
                "to": [recipient],
                "subject": "Restablece tu contraseña de Nexova",
                "text": (
                    "Solicitaste restablecer tu contraseña de Nexova. "
                    f"Usa este enlace temporal: {reset_url}"
                ),
            }
        ).encode("utf-8")
        request = Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status < 200 or response.status >= 300:
                    raise EmailDeliveryError("Email provider rejected the message")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise EmailDeliveryError("Email provider is unavailable") from exc