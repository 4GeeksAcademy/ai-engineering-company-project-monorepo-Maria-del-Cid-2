"""Tests for the in-memory TTL cache utility."""

from __future__ import annotations

import time as _time
import unittest
from unittest import mock

from app.cache import TTLCache


class TTLCacheTests(unittest.TestCase):
    """Unit tests for TTLCache."""

    def test_get_nonexistent_key_returns_none(self) -> None:
        cache: TTLCache[str] = TTLCache()
        self.assertIsNone(cache.get("missing"))

    def test_set_and_get(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")

    def test_get_expired_entry_returns_none(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key", "value", ttl=0.001)
        _time.sleep(0.002)
        self.assertIsNone(cache.get("key"))

    def test_expired_entry_is_removed_from_store(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key", "value", ttl=0.001)
        _time.sleep(0.002)
        self.assertIsNone(cache.get("key"))
        self.assertEqual(cache.size, 0)

    def test_ttl_default_from_constructor(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl=60)
        cache.set("key", "value")
        # Should not expire for a while
        self.assertEqual(cache.get("key"), "value")

    def test_explicit_ttl_overrides_default(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl=60)
        cache.set("key", "value", ttl=0.001)
        _time.sleep(0.002)
        self.assertIsNone(cache.get("key"))

    def test_delete_removes_key(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.delete("k1")
        self.assertIsNone(cache.get("k1"))
        self.assertEqual(cache.get("k2"), "v2")

    def test_delete_nonexistent_key_is_noop(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.delete("missing")  # should not raise

    def test_clear_removes_all(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        self.assertIsNone(cache.get("a"))
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.size, 0)

    def test_invalidate_prefix(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("product:1", "a")
        cache.set("product:2", "b")
        cache.set("other", "c")
        removed = cache.invalidate("product:")
        self.assertCountEqual(removed, ["product:1", "product:2"])
        self.assertIsNone(cache.get("product:1"))
        self.assertIsNone(cache.get("product:2"))
        self.assertEqual(cache.get("other"), "c")

    def test_invalidate_no_match(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key", "value")
        removed = cache.invalidate("nonexistent:")
        self.assertEqual(removed, [])
        self.assertEqual(cache.get("key"), "value")

    def test_size_accounting(self) -> None:
        cache: TTLCache[str] = TTLCache()
        self.assertEqual(cache.size, 0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        self.assertEqual(cache.size, 2)
        cache.clear()
        self.assertEqual(cache.size, 0)

    def test_cached_none_vs_missing(self) -> None:
        """A value of None is a valid cached value different from 'missing'."""
        cache: TTLCache[str | None] = TTLCache()
        cache.set("nullable", None)
        # Should return None (the cached value), not silently drop it
        self.assertIsNone(cache.get("nullable"))
        # But a truly missing key also returns None, so we can't distinguish
        # externally — that's a known limitation documented in the module.
        self.assertIsNone(cache.get("truly_missing"))

    def test_default_ttl_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            TTLCache(default_ttl=0)
        with self.assertRaises(ValueError):
            TTLCache(default_ttl=-1)

    def test_set_with_non_positive_ttl_raises(self) -> None:
        cache: TTLCache[str] = TTLCache()
        with self.assertRaises(ValueError):
            cache.set("key", "value", ttl=0)
        with self.assertRaises(ValueError):
            cache.set("key", "value", ttl=-5)

    def test_remove_expired_helper(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl=60)
        cache.set("fresh", "ok")
        cache.set("stale", "bad", ttl=0.001)
        _time.sleep(0.002)
        removed = cache._remove_expired()
        self.assertEqual(removed, 1)
        self.assertIsNotNone(cache.get("fresh"))

    def test_set_updates_existing_key_ttl(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key", "old", ttl=0.001)
        _time.sleep(0.002)
        self.assertIsNone(cache.get("key"))
        # Re-set with a longer TTL
        cache.set("key", "new", ttl=60)
        self.assertEqual(cache.get("key"), "new")

    def test_time_monotonic_used_for_expiry(self) -> None:
        """Verify that the expiry check uses time.monotonic, not time.time."""
        cache: TTLCache[str] = TTLCache(default_ttl=30)
        fixed_now = 1_000_000.0

        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now):
            cache.set("k", "v", ttl=10)

        # Within TTL
        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now + 5):
            self.assertEqual(cache.get("k"), "v")

        # Just before expiration
        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now + 9.999):
            self.assertEqual(cache.get("k"), "v")

        # Past expiry (at the exact boundary the entry is already expired)
        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now + 10.001):
            self.assertIsNone(cache.get("k"))