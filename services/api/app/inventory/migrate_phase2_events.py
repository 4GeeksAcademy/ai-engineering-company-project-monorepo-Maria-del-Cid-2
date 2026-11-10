"""Explicitly migrate approved Phase 2 inventory valuation/event tables."""

from __future__ import annotations

import argparse

from sqlalchemy.engine import make_url

from .database import get_database_url, get_engine
from .migrate_programmes import migrate_phase2_events, migrate_programmes
from .seed import validate_seed_target


def main() -> None:
    parser = argparse.ArgumentParser(description="Add inventory thresholds, valuation, and kit configuration.")
    parser.add_argument("--environment", choices=("development", "test"), required=True)
    args = parser.parse_args()
    database_url = get_database_url()
    validate_seed_target(args.environment, database_url)
    target = make_url(database_url)
    if target.get_backend_name() == "sqlite" and target.database != ":memory:":
        from pathlib import Path

        if not Path(target.database or "").is_file():
            raise RuntimeError("Inventory database file does not exist; migration cancelled.")
    engine = get_engine()
    migrate_programmes(engine)
    migrate_phase2_events(engine)
    print("Inventory Phase 2 events migration completed (programmes/outbox included if needed).")


if __name__ == "__main__":
    main()