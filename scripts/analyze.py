#!/usr/bin/env python3
"""Command-line interface for Nexova Incident Analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPOSITORY_ROOT / "services" / "api"))

from app.incidents.analysis import analyze_incidents_csv  # noqa: E402
from app.incidents.export import export_analysis_csv  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a Nexova incidents CSV file.")
    parser.add_argument("csv_path", type=Path, help="path to the incidents CSV file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        result = analyze_incidents_csv(args.csv_path)
    except (OSError, ValueError) as exc:
        print(f"Error: unable to analyze CSV: {exc}", file=sys.stderr)
        return 1

    _print_report(args.csv_path, result)
    answer = input("Export results to CSV? [y / n]: ").strip().lower()
    if answer == "y":
        try:
            export_analysis_csv(result, Path("results.csv"))
        except OSError as exc:
            print(f"Error: unable to export results: {exc}", file=sys.stderr)
            return 1
        print("Results exported to results.csv")
    return 0


def _print_report(source: Path, result: object) -> None:
    # Importing the concrete model only for display keeps the public entrypoint
    # small while all calculations remain in the domain analysis engine.
    from app.incidents.models import IncidentAnalysisResult

    assert isinstance(result, IncidentAnalysisResult)
    print("=" * 60)
    print("  NEXOVA — SUPPORT TICKET ANALYSIS")
    print(f"  Source file: {source}")
    print("=" * 60)
    print()
    print(f"TOTAL RECORDS IN FILE .......... {result.total_records}")
    print(f"  ├─ Valid records ................ {result.valid_records}")
    print(f"  └─ Invalid / incomplete .......... {result.invalid_records}")
    print()
    print("INVALID RECORDS BREAKDOWN")
    for code, count in result.invalid_by_type.items():
        print(f"  ├─ {code.value} ........ {count}")
    print()
    print("BREAKDOWN BY CATEGORY (valid records)")
    for category, count in result.by_category.items():
        percentage = count / result.valid_records * 100 if result.valid_records else 0
        print(f"  ├─ {category.value} ........ {count} ({percentage:.1f}%)")
    print()
    print("BREAKDOWN BY STATUS (valid records)")
    for status, count in result.by_status.items():
        percentage = count / result.valid_records * 100 if result.valid_records else 0
        print(f"  ├─ {status.value} ........ {count} ({percentage:.1f}%)")
    print()
    print("SATISFACTION INDEX (closed tickets)")
    scored = sum(result.satisfaction_distribution.values())
    print(f"  Scored tickets: {scored} of {result.by_status.get('CLOSED', 0)}")
    average = "N/A" if result.average_satisfaction is None else f"{result.average_satisfaction:.2f} / 5.00"
    print(f"  Average score: {average}")
    for score, count in result.satisfaction_distribution.items():
        print(f"  ├─ Score {score} ................ {count}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    raise SystemExit(main())
