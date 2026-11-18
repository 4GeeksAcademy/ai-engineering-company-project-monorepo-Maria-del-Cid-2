"""Local Redis/Celery integration test; worker runs in-process with pool=solo."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg
from celery.result import AsyncResult

from celery.contrib.testing.worker import start_worker
from fastapi.testclient import TestClient

from app.celery_app import celery_app
from app.main import app
from app.tasks.incident_analysis import _remove_input, analyze_incidents_task

CSV_CONTENT = (
    "ticket_id,date,client_company,category,description,agent_id,status,customer_email,satisfaction_score\n"
    "NXV-1,2024-01-01,Acme,ACCESS,issue,AGT-1,OPEN,person@example.com,\n"
)


class LocalCeleryIncidentAnalysisIntegrationTests(unittest.TestCase):
    def test_http_enqueue_worker_result_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as upload_dir:
            previous_upload_dir = os.environ.get("INCIDENT_ANALYSIS_UPLOAD_DIR")
            os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = upload_dir
            queue_name = f"incident-analysis-test-{uuid.uuid4().hex}"
            try:
                with patch.dict(
                    celery_app.conf,
                    {"task_default_queue": queue_name, "task_default_routing_key": queue_name},
                ):
                    with start_worker(
                        celery_app,
                        pool="solo",
                        loglevel="ERROR",
                        perform_ping_check=False,
                        concurrency=1,
                        queues=[queue_name],
                    ) as worker:
                        self.assertIn(analyze_incidents_task.name, worker.consumer.strategies)
                        with patch(
                            "app.tasks.incident_analysis._remove_input",
                            wraps=_remove_input,
                        ) as remove_input:
                            with TestClient(app) as client:
                                response = client.post(
                                    "/api/incidents/analyze",
                                    files={"file": ("incidents.csv", CSV_CONTENT, "text/csv")},
                                )
                                self.assertEqual(response.status_code, 202, response.text)
                                task_id = response.json()["task_id"]
                                deadline = time.monotonic() + 20
                                status_response = None
                                while time.monotonic() < deadline:
                                    status_response = client.get(f"/api/tasks/{task_id}")
                                    if status_response.json()["status"] in {"success", "failure"}:
                                        break
                                    time.sleep(0.1)
                                self.assertIsNotNone(status_response)
                                self.assertEqual(status_response.status_code, 200)
                                payload = status_response.json()
                                task_result = AsyncResult(task_id, app=celery_app)
                                self.assertEqual(
                                    payload["status"],
                                    "success",
                                    {
                                        "status": payload["status"],
                                        "exception_type": type(task_result.result).__name__,
                                    },
                                )
                                self.assertEqual(payload["result"]["total_records"], 1)
                                self.assertNotIn("person@example.com", status_response.text)
                                remove_input.assert_called_once()
                                self.assertFalse(remove_input.call_args.args[0].exists())
            finally:
                if previous_upload_dir is None:
                    os.environ.pop("INCIDENT_ANALYSIS_UPLOAD_DIR", None)
                else:
                    os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = previous_upload_dir

    @unittest.skipUnless(os.environ.get("CELERY_DATABASE_URL"), "requires configured CELERY_DATABASE_URL")
    def test_terminal_failure_is_persisted_once_and_csv_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as upload_dir:
            previous_upload_dir = os.environ.get("INCIDENT_ANALYSIS_UPLOAD_DIR")
            os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = upload_dir
            upload_id = "8fa7f66fbad94585ae8dbb19e2b38666"
            input_path = Path(upload_dir) / f"{upload_id}.csv"
            input_path.write_text(CSV_CONTENT, encoding="utf-8")
            queue_name = f"incident-analysis-test-{uuid.uuid4().hex}"
            task_id = uuid.uuid4().hex
            result = None
            row = None
            previous_upload_dir = os.environ.get("INCIDENT_ANALYSIS_UPLOAD_DIR")
            try:
                with patch.dict(
                    celery_app.conf,
                    {"task_default_queue": queue_name, "task_default_routing_key": queue_name},
                ):
                    with start_worker(
                        celery_app,
                        pool="solo",
                        loglevel="ERROR",
                        perform_ping_check=False,
                        concurrency=1,
                        queues=[queue_name],
                    ):
                        with patch(
                            "app.tasks.incident_analysis.analyze_incidents",
                            side_effect=OSError(5, "deterministic transient test failure"),
                        ):
                            result = analyze_incidents_task.apply_async(args=[upload_id], task_id=task_id)
                            try:
                                result.get(timeout=20, propagate=False)
                            except TimeoutError:
                                self.fail("Celery task did not reach a terminal state")
                    self.assertEqual(result.state, "FAILURE")
                    callback_completed = False
                    cleanup_deadline = time.monotonic() + 5
                    while time.monotonic() < cleanup_deadline:
                        with psycopg.connect(os.environ["CELERY_DATABASE_URL"], sslmode="require") as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "SELECT attempt_count, error_type FROM public.celery_incident_analysis_dlq "
                                    "WHERE task_id = %s",
                                    (task_id,),
                                )
                                row = cur.fetchone()
                        if row is not None:
                            callback_completed = True
                            break
                        time.sleep(0.05)
                    self.assertTrue(callback_completed, "terminal failure hook did not persist the DLQ record")
                    self.assertEqual(row, (3, "OSError"))
                    self.assertFalse(input_path.exists())
                    with psycopg.connect(os.environ["CELERY_DATABASE_URL"], sslmode="require") as conn:
                        self.assertTrue(conn.pgconn.ssl_in_use)
            finally:
                with psycopg.connect(os.environ["CELERY_DATABASE_URL"], sslmode="require") as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM public.celery_incident_analysis_dlq WHERE task_id = %s",
                            (task_id,),
                        )
                if previous_upload_dir is None:
                    os.environ.pop("INCIDENT_ANALYSIS_UPLOAD_DIR", None)
                else:
                    os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = previous_upload_dir

        def test_transient_failure_retries_then_succeeds(self) -> None:
            with tempfile.TemporaryDirectory() as upload_dir:
                os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = upload_dir
                upload_id = uuid.uuid4().hex
                input_path = Path(upload_dir) / f"{upload_id}.csv"
                input_path.write_text(CSV_CONTENT, encoding="utf-8")
                queue_name = f"incident-analysis-test-{uuid.uuid4().hex}"
                task_id = uuid.uuid4().hex
                from app.tasks import incident_analysis as task_module

                original_analyzer = task_module.analyze_incidents
                invocation_count = 0

                def fail_once(rows):
                    nonlocal invocation_count
                    invocation_count += 1
                    if invocation_count == 1:
                        raise OSError(5, "temporary test read failure")
                    return original_analyzer(rows)

                try:
                    with patch.dict(
                        celery_app.conf,
                        {"task_default_queue": queue_name, "task_default_routing_key": queue_name},
                    ):
                        with start_worker(
                            celery_app,
                            pool="solo",
                            loglevel="ERROR",
                            perform_ping_check=False,
                            concurrency=1,
                            queues=[queue_name],
                        ):
                            with patch.object(task_module, "analyze_incidents", side_effect=fail_once):
                                result = analyze_incidents_task.apply_async(args=[upload_id], task_id=task_id)
                                payload = result.get(timeout=20)
                    self.assertEqual(result.state, "SUCCESS")
                    self.assertEqual(invocation_count, 2)
                    self.assertEqual(payload["total_records"], 1)
                    self.assertFalse(input_path.exists())
                finally:
                    if previous_upload_dir is None:
                        os.environ.pop("INCIDENT_ANALYSIS_UPLOAD_DIR", None)
                    else:
                        os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = previous_upload_dir


if __name__ == "__main__":
    unittest.main()
