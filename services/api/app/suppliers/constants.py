"""Constants for the Nexova Supplier Directory domain."""

from typing import Final

VALID_COUNTRIES: Final[tuple[str, ...]] = ("Spain", "USA")
VALID_CURRENCIES: Final[tuple[str, ...]] = ("EUR", "USD")
VALID_CATEGORIES: Final[tuple[str, ...]] = (
    "job_boards",
    "ats_software",
    "assessment_tools",
    "training_platforms",
    "payroll_and_hr_software",
    "video_interview",
    "background_check",
    "office_and_facilities",
    "it_and_software_licenses",
)
VALID_STATUSES: Final[tuple[str, ...]] = ("active", "suspended")

CURRENCY_BY_COUNTRY: Final[dict[str, str]] = {
    "Spain": "EUR",
    "USA": "USD",
}
