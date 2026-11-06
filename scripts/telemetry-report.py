#!/usr/bin/env python3
"""CLI wrapper for the Pandas Telemetry Analytics pipeline.

Usage::

    python scripts/telemetry-report.py
    python scripts/telemetry-report.py --start 2026-11-01 --end 2026-11-07
    python scripts/telemetry-report.py --limit 500 --output dashboard.html
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the services/api package is importable
_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_PKG = _REPO_ROOT / "services" / "api"
sys.path.insert(0, str(_API_PKG.resolve()))

from app.telemetry.report import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
