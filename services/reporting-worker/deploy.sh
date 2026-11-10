#!/bin/sh
set -eu

cd /app
echo "Waiting for Prefect API at ${PREFECT_API_URL}"
uv run --project /app/services/api python - <<'PY'
import time
import urllib.error
import urllib.request

url = "http://prefect-server:4200/api/health"
for attempt in range(60):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status == 200:
                print("Prefect API is ready")
                break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(2)
else:
    raise SystemExit("Prefect API did not become ready")
PY
uv run --project /app/services/api prefect work-pool create reporting-process-pool --type process --overwrite
uv run --project /app/services/api prefect deploy --prefect-file /app/services/reporting-worker/prefect.yaml --all --no-prompt
