"""Docker integration test for publisher/retention locks on a named volume.

Run after building the scheduler image:
    services/api/.venv/Scripts/python.exe -m pytest services/tests/test_docker_shared_volume_lock.py -q

The test creates and removes only a uniquely named temporary Docker volume and
containers. It never mounts the operational nightly_export_audit volume.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _docker(*args: str, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(
            f"docker {' '.join(args[:3])} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
    return result


def _wait_for_marker(container: str, marker: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _docker(
            "exec", container, "python", "-c",
            f"from pathlib import Path; raise SystemExit(0 if Path('/probe/{marker}').exists() else 1)",
            check=False,
        )
        if result.returncode == 0:
            return
        state = _docker("inspect", "--format", "{{.State.Status}}", container, check=False)
        if state.returncode or state.stdout.strip() != "running":
            raise AssertionError(f"owner container stopped before creating /probe/{marker}")
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for /probe/{marker}")


def test_shared_volume_lock_blocks_retention_and_releases_on_exit() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")
    available = _docker("info", check=False)
    if available.returncode:
        pytest.skip("Docker daemon is unavailable")

    image_id = os.environ.get("NIGHTLY_SCHEDULER_TEST_IMAGE", "").strip()
    if not image_id:
        image_result = _docker("compose", "images", "-q", "nightly-scheduler", check=False)
        image_id = image_result.stdout.strip().splitlines()[0] if image_result.stdout.strip() else ""
    if not image_id:
        pytest.skip("Build nightly-scheduler first or set NIGHTLY_SCHEDULER_TEST_IMAGE")
    retention_image = os.environ.get("RETENTION_SCHEDULER_TEST_IMAGE", "").strip()
    if not retention_image:
        if image_id.endswith("-nightly-scheduler:latest"):
            retention_image = image_id.removesuffix("-nightly-scheduler:latest") + "-retention-scheduler:latest"
        else:
            pytest.skip("Set RETENTION_SCHEDULER_TEST_IMAGE for a nonstandard nightly image tag")

    suffix = uuid.uuid4().hex[:12]
    volume = f"nexova-locktest-{suffix}"
    graceful_owner = f"nexova-locktest-graceful-{suffix}"
    abrupt_owner = f"nexova-locktest-abrupt-{suffix}"
    created_volume = False
    containers: list[str] = []
    artifact = "/probe/telemetry-events-2000-01-01.csv"
    mount = f"type=volume,source={volume},target=/probe"
    try:
        _docker("volume", "create", volume)
        created_volume = True

        owner_code = "\n".join(
            [
                "import time",
                "import os",
                "from pathlib import Path",
                "from csv_artifact_lock import artifact_lock",
                f"artifact = Path({artifact!r})",
                "with artifact_lock(artifact):",
                "    temporary = artifact.with_suffix(artifact.suffix + '.tmp')",
                "    temporary.write_text('temporary integration fixture', encoding='utf-8')",
                "    os.replace(temporary, artifact)",
                "    Path('/probe/locked').touch()",
                "    print('LOCKED', flush=True)",
                "    while not Path('/probe/release').exists(): time.sleep(0.05)",
            ]
        )
        _docker(
            "run", "-d", "--name", graceful_owner, "--mount", mount,
            image_id, "python", "-u", "-c", owner_code,
        )
        containers.append(graceful_owner)
        _wait_for_marker(graceful_owner, "locked")

        direct_probe = "\n".join(
            [
                "from pathlib import Path",
                "from csv_artifact_lock import LockBusyError, artifact_lock",
                f"artifact = Path({artifact!r})",
                "try:",
                "    with artifact_lock(artifact, blocking=False): pass",
                "except LockBusyError:",
                "    print('LockBusy')",
                "else:",
                "    raise SystemExit('unexpectedly acquired held lock')",
            ]
        )
        contention = _docker(
            "run", "--rm", "--mount", mount, image_id, "python", "-c", direct_probe
        )
        assert "LockBusy" in contention.stdout

        retention = _docker(
            "run", "--rm", "--mount", mount, retention_image,
            "python", "/app/scripts/retention_manager.py", "--directory", "/probe",
        )
        retention_logs = retention.stdout + retention.stderr
        assert '"result": "skipped_in_use"' in retention_logs, retention_logs
        exists_while_locked = _docker(
            "exec", graceful_owner, "python", "-c",
            f"from pathlib import Path; raise SystemExit(0 if Path({artifact!r}).exists() else 1)",
            check=False,
        )
        assert exists_while_locked.returncode == 0, "retention deleted a file under publisher lock"

        _docker(
            "exec", graceful_owner, "python", "-c",
            "from pathlib import Path; Path('/probe/release').touch()",
        )
        exited = _docker("wait", graceful_owner)
        assert exited.stdout.strip() == "0"
        unlocked = "\n".join(
            [
                "from pathlib import Path",
                "from csv_artifact_lock import artifact_lock",
                f"artifact = Path({artifact!r})",
                "with artifact_lock(artifact, blocking=False): print('ACQUIRED')",
            ]
        )
        acquired_after_release = _docker(
            "run", "--rm", "--mount", mount, image_id, "python", "-c", unlocked
        )
        assert "ACQUIRED" in acquired_after_release.stdout

        deleted_after_release = _docker(
            "run", "--rm", "--mount", mount, retention_image,
            "python", "/app/scripts/retention_manager.py", "--directory", "/probe",
        )
        deletion_logs = deleted_after_release.stdout + deleted_after_release.stderr
        assert '"result": "deleted"' in deletion_logs, deletion_logs
        assert _docker(
            "run", "--rm", "--mount", mount, image_id, "python", "-c",
            f"from pathlib import Path; raise SystemExit(1 if Path({artifact!r}).exists() else 0)",
        ).returncode == 0

        abrupt_code = "\n".join(
            [
                "import time",
                "from pathlib import Path",
                "from csv_artifact_lock import artifact_lock",
                f"artifact = Path({artifact!r})",
                "artifact.write_text('temporary abrupt-exit fixture', encoding='utf-8')",
                "with artifact_lock(artifact):",
                "    Path('/probe/abrupt-locked').touch()",
                "    print('LOCKED', flush=True)",
                "    while True: time.sleep(1)",
            ]
        )
        _docker(
            "run", "-d", "--name", abrupt_owner, "--mount", mount,
            image_id, "python", "-u", "-c", abrupt_code,
        )
        containers.append(abrupt_owner)
        _wait_for_marker(abrupt_owner, "abrupt-locked")
        _docker("kill", abrupt_owner)
        _docker("wait", abrupt_owner)
        acquired_after_kill = _docker(
            "run", "--rm", "--mount", mount, image_id, "python", "-c", unlocked
        )
        assert "ACQUIRED" in acquired_after_kill.stdout
    finally:
        for container in containers:
            _docker("rm", "-f", container, check=False)
        if created_volume:
            _docker("volume", "rm", volume, check=False)
