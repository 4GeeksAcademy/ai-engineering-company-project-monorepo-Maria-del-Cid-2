"""Pydantic contracts for Supplier Directory data."""

from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .constants import CURRENCY_BY_COUNTRY, VALID_CATEGORIES, VALID_COUNTRIES

Country = Literal["Spain", "USA"]
Currency = Literal["EUR", "USD"]
SupplierStatus = Literal["active", "suspended"]
Category = Literal[
    "job_boards",
    "ats_software",
    "assessment_tools",
    "training_platforms",
    "payroll_and_hr_software",
    "video_interview",
    "background_check",
    "office_and_facilities",
    "it_and_software_licenses",
]

NonEmptyName = Annotated[str, Field(min_length=1)]
PositiveRate = Annotated[float, Field(gt=0)]


class SupplierFields(BaseModel):
    """Client-supplied fields shared by create and persisted supplier models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: NonEmptyName
    country: Country
    categories: list[Category] = Field(min_length=1)
    monthly_rate: PositiveRate
    currency: Currency
    status: SupplierStatus
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def categories_must_be_unique(cls, categories: list[Category]) -> list[Category]:
        if len(categories) != len(set(categories)):
            raise ValueError("categories must not contain duplicates")
        return categories

    @model_validator(mode="after")
    def currency_must_match_country(self) -> "SupplierFields":
        expected_currency = CURRENCY_BY_COUNTRY[self.country]
        if self.currency != expected_currency:
            raise ValueError(
                f"currency must be {expected_currency} when country is {self.country}"
            )
        return self


class SupplierCreate(SupplierFields):
    """Payload accepted when creating a supplier."""


class SupplierRateUpdate(BaseModel):
    """Payload accepted when changing a supplier's monthly rate."""

    model_config = ConfigDict(extra="forbid")

    monthly_rate: PositiveRate


class SupplierStatusUpdate(BaseModel):
    """Payload accepted when changing a supplier's status."""

    model_config = ConfigDict(extra="forbid")

    status: SupplierStatus


class Supplier(SupplierFields):
    """Persisted supplier returned by the API."""

    id: int = Field(gt=0)
    updated_at: datetime

    @classmethod
    def from_create(cls, supplier_id: int, payload: SupplierCreate) -> "Supplier":
        return cls(
            id=supplier_id,
            updated_at=datetime.now(timezone.utc),
            **payload.model_dump(),
        )


# Keep these names available for future route/database code without duplicating
# the domain vocabulary in adapters.
__all__ = [
    "Category",
    "Country",
    "Currency",
    "Supplier",
    "SupplierCreate",
    "SupplierRateUpdate",
    "SupplierStatusUpdate",
    "SupplierStatus",
    "VALID_CATEGORIES",
    "VALID_COUNTRIES",
]
