"""Seed approved training programmes only in an explicit development/test DB."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlmodel import Session

from .database import get_engine
from .models import Programme
from .seed import SeedSafetyError, validate_seed_target


PROGRAMMES = (
    ("prog-digital-skills-001", "Digital Skills & AI Foundations"),
    ("prog-technical-onboarding-001", "Technical Onboarding Programme"),
    ("prog-professional-development-001", "Professional Development Programme"),
)


def seed_programmes(session: Session) -> int:
    if session.in_transaction():
        raise SeedSafetyError("Seed requires a clean session.")
    inserted = 0
    with session.begin():
        for programme_id, name in PROGRAMMES:
            existing = session.get(Programme, programme_id)
            if existing is not None:
                if existing.name != name:
                    raise SeedSafetyError(f"Programme {programme_id} has different data.")
                continue
            session.add(Programme(programme_id=programme_id, name=name))
            inserted += 1
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed approved training programmes in a test/development inventory DB.")
    parser.add_argument("--environment", choices=("development", "test"), required=True)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL", "")
    validate_seed_target(args.environment, database_url)
    target = make_url(database_url)
    if target.get_backend_name() == "sqlite" and not Path(target.database or "").is_file():
        raise SeedSafetyError("Inventory database file does not exist.")
    with Session(get_engine()) as session:
        inserted = seed_programmes(session)
    print(f"Programmes inserted: {inserted}")


if __name__ == "__main__":
    main()