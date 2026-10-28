"""ASGI middleware that logs the duration of each HTTP request.

The middleware records the start time before delegating to the inner app,
captures the response status code, and logs method, path, status and wall-clock
duration in milliseconds.

Log format (one line per request)::

    method=GET path=/api/inventory/products status=200 duration_ms=45.2

Security / privacy
------------------
- Request bodies are never read or logged.
- The ``Authorization`` header, sensitive query parameters, and client IPs are
  never inspected or logged.
- Exceptions are **not** caught — the timing of a failed request is still
  recorded inside a ``finally`` block and the exception is re-raised without
  any modification to the error flow.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class TimingMiddleware:
    """Logs method, path, status code and wall-clock duration per request.

    Usage in a FastAPI application::

        from app.middleware import TimingMiddleware

        app.add_middleware(TimingMiddleware)

    The middleware must be added after CORS so that the measured duration
    reflects the actual request processing inside the application layer.
    """

    __slots__ = ("app",)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only measure HTTP requests; ignore WebSocket and other ASGI types.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        # Default to 500 — will be overwritten once the response starts.
        status_code: int = 500

        async def _send_wrapper(message: dict) -> None:
            """Intercept the response-start message to read the status code."""
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", status_code)
            await send(message)

        try:
            await self.app(scope, receive, _send_wrapper)
        except Exception:
            # The duration of a failed request is still logged; the exception
            # is unconditionally re-raised so that existing error handlers
            # (exception_handlers on FastAPI) continue to work unchanged.
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            logger.info(
                "method=%s path=%s status=%d duration_ms=%.2f",
                method,
                path,
                status_code,
                duration_ms,
            )