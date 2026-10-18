"""Isolated tests for the future inventory SQLModel persistence boundary."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlmodel import Session
from sqlalchemy import event

from app.inventory import database


class InventoryDatabaseTests(unittest.TestCase):
    def tearDown(self) -> None:
        database.clear_engine_cache()

    def test_missing_database_url_fails_without_engine_creation(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                database.get_database_url()

            with self.assertRaises(HTTPException) as raised:
                next(database.get_session())

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(database.get_engine.cache_info().currsize, 0)

    def test_sqlite_engine_is_lazy_and_cached(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database_file = Path(temporary_directory) / "inventory-test.sqlite3"
            url = f"sqlite:///{database_file}"
            with patch.dict(os.environ, {database.DATABASE_URL_ENV: url}):
                engine = database.get_engine()
                connection_events: list[str] = []
                event.listen(engine, "connect", lambda *_: connection_events.append("connect"))

                self.assertEqual(str(engine.url), url)
                self.assertIs(database.get_engine(), engine)
                self.assertEqual(connection_events, [])
                self.assertFalse(database_file.exists())

                with engine.connect():
                    pass

                self.assertEqual(connection_events, ["connect"])
                self.assertTrue(database_file.exists())
                database.clear_engine_cache()

    def test_session_dependency_closes_session_on_normal_close(self) -> None:
        class SessionSpy:
            was_closed = False

            def close(self) -> None:
                self.was_closed = True

        spy = SessionSpy()
        with patch.object(database, "get_engine", return_value=object()), patch.object(
            database, "Session", return_value=spy
        ):
            dependency = database.get_session()
            self.assertIs(next(dependency), spy)
            dependency.close()

        self.assertTrue(spy.was_closed)

    def test_session_dependency_closes_session_when_error_is_thrown(self) -> None:
        class SessionSpy:
            was_closed = False

            def close(self) -> None:
                self.was_closed = True

        spy = SessionSpy()
        with patch.object(database, "get_engine", return_value=object()), patch.object(
            database, "Session", return_value=spy
        ):
            dependency = database.get_session()
            self.assertIs(next(dependency), spy)
            with self.assertRaisesRegex(ValueError, "route failure"):
                dependency.throw(ValueError("route failure"))

        self.assertTrue(spy.was_closed)


if __name__ == "__main__":
    unittest.main()
