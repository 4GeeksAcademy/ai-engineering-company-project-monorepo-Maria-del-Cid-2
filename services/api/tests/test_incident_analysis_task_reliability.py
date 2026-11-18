from __future__ import annotations

import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from celery.exceptions import Retry

from app.incidents.dlq import IncidentAnalysisDlqRepository
from app.tasks.incident_analysis import (
    IncidentAnalysisTask,
    _is_transient_failure,
    analyze_incidents_task,
)

UPLOAD_ID = "8fa7f66fbad94585ae8dbb19e2b38666"
CSV_CONTENT = (
    "ticket_id,date,client_company,category,description,agent_id,status,customer_email,satisfaction_score\n"
    "NXV-1,2024-01-01,Acme,ACCESS,issue,AGT-1,OPEN,person@example.com,\n"
)


class IncidentAnalysisRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"INCIDENT_ANALYSIS_UPLOAD_DIR": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = Path(self.temp_dir.name) / f"{UPLOAD_ID}.csv"
        self.path.write_text(CSV_CONTENT, encoding="utf-8")

    def test_task_allows_exactly_two_retries(self) -> None:
        self.assertEqual(analyze_incidents_task.max_retries, 2)

    def test_transient_error_schedules_exponential_retry_and_keeps_csv(self) -> None:
        with patch("app.tasks.incident_analysis.read_incidents_csv", side_effect=TimeoutError()):
            with patch.object(analyze_incidents_task, "retry", side_effect=Retry()) as retry:
                analyze_incidents_task.push_request(retries=0)
                self.addCleanup(analyze_incidents_task.pop_request)
                with self.assertRaises(Retry):
                    analyze_incidents_task.run(UPLOAD_ID)
        retry.assert_called_once()
        self.assertEqual(retry.call_args.kwargs["countdown"], 1)
        self.assertTrue(self.path.exists())

    def test_second_retry_uses_two_second_backoff(self) -> None:
        with patch("app.tasks.incident_analysis.read_incidents_csv", side_effect=ConnectionError()):
            with patch.object(analyze_incidents_task, "retry", side_effect=Retry()) as retry:
                analyze_incidents_task.push_request(retries=1)
                self.addCleanup(analyze_incidents_task.pop_request)
                with self.assertRaises(Retry):
                    analyze_incidents_task.run(UPLOAD_ID)
        self.assertEqual(retry.call_args.kwargs["countdown"], 2)
        self.assertTrue(self.path.exists())

    def test_third_transient_failure_is_terminal_without_more_retry(self) -> None:
        with patch("app.tasks.incident_analysis.read_incidents_csv", side_effect=TimeoutError()):
            with patch.object(analyze_incidents_task, "retry") as retry:
                analyze_incidents_task.push_request(retries=2)
                self.addCleanup(analyze_incidents_task.pop_request)
                with self.assertRaises(TimeoutError):
                    analyze_incidents_task.run(UPLOAD_ID)
        retry.assert_not_called()
        self.assertTrue(self.path.exists(), "terminal callback performs cleanup after on_failure")

    def test_success_removes_csv(self) -> None:
        result = analyze_incidents_task.run(UPLOAD_ID)
        self.assertEqual(result["total_records"], 1)
        self.assertFalse(self.path.exists())

    def test_failure_classifier_retries_transient_only(self) -> None:
        self.assertTrue(_is_transient_failure(TimeoutError()))
        self.assertTrue(_is_transient_failure(OSError(errno.EIO, "I/O")))
        self.assertTrue(_is_transient_failure(OSError(errno.ETIMEDOUT, "timeout")))
        self.assertFalse(_is_transient_failure(ValueError("invalid input")))
        self.assertFalse(_is_transient_failure(OSError(errno.EACCES, "permission")))

    def test_terminal_failure_hook_persists_sanitized_metadata_and_cleans_csv(self) -> None:
        task = analyze_incidents_task
        task.push_request(retries=2)
        self.addCleanup(task.pop_request)
        with patch("app.incidents.dlq.IncidentAnalysisDlqRepository.record_failure") as record:
            task.on_failure(
                ValueError("raw customer data must not be sent"),
                "celery-task-id",
                (UPLOAD_ID,),
                {},
                None,
            )
        record.assert_called_once_with(
            task_id="celery-task-id",
            task_name="nexova.incidents.analyze",
            attempt_count=3,
            exception_type="ValueError",
        )
        self.assertFalse(self.path.exists())


class IncidentAnalysisDlqRepositoryTests(unittest.TestCase):
    def test_upsert_is_idempotent_and_connection_requires_ssl(self) -> None:
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.pgconn.ssl_in_use = True
        connection.cursor.return_value = cursor
        connect = Mock(return_value=connection)
        repo = IncidentAnalysisDlqRepository(connect=connect)
        with patch.dict(os.environ, {"CELERY_DATABASE_URL": "postgresql://placeholder/database"}):
            for _ in range(2):
                repo.record_failure(
                    task_id="celery-task-id",
                    task_name="nexova.incidents.analyze",
                    attempt_count=3,
                    exception_type="TimeoutError",
                )
        self.assertEqual(connect.call_args.kwargs["sslmode"], "require")
        self.assertIn("ON CONFLICT (task_id) DO UPDATE", cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(connection.commit.call_count, 2)

    def test_repository_does_not_store_exception_message(self) -> None:
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.pgconn.ssl_in_use = True
        connection.cursor.return_value = cursor
        with patch.dict(os.environ, {"CELERY_DATABASE_URL": "postgresql://placeholder/database"}):
            IncidentAnalysisDlqRepository(connect=Mock(return_value=connection)).record_failure(
                task_id="celery-task-id",
                task_name="nexova.incidents.analyze",
                attempt_count=3,
                exception_type="TimeoutError",
            )
        self.assertNotIn("message", cursor.execute.call_args.args[0].lower())
        self.assertNotIn("private detail", repr(cursor.execute.call_args.args[1]))


if __name__ == "__main__":
    unittest.main()
