"""In-memory TTL-based cache utility.

This module provides a lightweight, zero-dependency cache that stores values
in a plain dictionary and evicts entries whose time-to-live has expired.

Thread safety
-------------
The cache uses a standard ``dict`` under the hood.  In the context of an ASGI
application each request runs in its own coroutine on a single thread, so no
locking is needed.  If the cache were ever shared across threads, callers
would need to wrap access with their own lock.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")

# Sentinel object so callers can distinguish "not found" from a cached None.
_NOT_FOUND: Any = object()


class TTLCache(Generic[T]):
    """A dictionary-like cache with per-key time-to-live expiration.

    Typical usage::

        cache: TTLCache[list[dict[str, Any]]] = TTLCache(default_ttl=30)

        # Set with the default TTL
        cache.set("products", products_list)

        # Set with an explicit TTL (in seconds)
        cache.set("summary", summary_dict, ttl=10)

        # Retrieve (returns None if missing or expired)
        data = cache.get("products")
        if data is None:
            data = fetch_products()
            cache.set("products", data)

        # Invalidate all keys starting with a prefix
        cache.invalidate("product:")
    """

    __slots__ = ("_default_ttl", "_store")

    def __init__(self, default_ttl: float = 30) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, T]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> T | None:
        """Return the cached value for *key*, or ``None`` when missing/expired.

        Expired entries are silently deleted on access.
        """
        entry = self._store.get(key, _NOT_FOUND)
        if entry is _NOT_FOUND:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T, ttl: float | None = None) -> None:
        """Store *value* under *key* with the given *ttl* (or the default)."""
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        if ttl_seconds <= 0:
            raise ValueError("ttl must be positive")
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        """Remove *key* from the cache.  No-op if the key does not exist."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove every entry from the cache."""
        self._store.clear()

    def invalidate(self, prefix: str) -> list[str]:
        """Remove all keys that start with *prefix*.

        Returns the list of removed keys (useful for logging or testing).
        """
        removed: list[str] = []
        for key in list(self._store):
            if key.startswith(prefix):
                del self._store[key]
                removed.append(key)
        return removed

    # ------------------------------------------------------------------
    # Helpers for introspection (used by tests and debugging)
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Return the number of entries currently stored (including expired)."""
        return len(self._store)

    def _remove_expired(self) -> int:
        """Remove and return the count of expired entries (internal helper)."""
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now >= exp]
        for key in expired:
            del self._store[key]
        return len(expired)