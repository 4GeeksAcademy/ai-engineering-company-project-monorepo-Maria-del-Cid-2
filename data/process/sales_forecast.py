"""Data preparation and causal features for Nexova monthly sales forecasting.

This module deliberately does not fit or invoke a forecasting model.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "raw" / "nexova_sales.csv"
EXPECTED_MONTHS = 120
TRAIN_START = pd.Timestamp("2016-01-01")
TRAIN_END = pd.Timestamp("2023-12-01")
TEST_START = pd.Timestamp("2024-01-01")
TEST_END = pd.Timestamp("2025-12-01")
LAGS = (1, 2, 3, 6, 12)
ROLLING_WINDOWS = (3, 6, 12)


def load_sales_data(path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Load, type, filter, sort, and validate consolidated monthly sales."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Sales dataset not found: {source}")

    frame = pd.read_csv(source)
    required = {
        "month",
        "revenue_usd",
        "active_contracts",
        "avg_contract_value_usd",
        "business_line",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = frame.loc[frame["business_line"].eq("consolidated")].copy()
    if frame.empty:
        raise ValueError("Dataset contains no consolidated records")

    frame["month"] = pd.to_datetime(frame["month"], errors="raise")
    numeric_columns = ("revenue_usd", "active_contracts", "avg_contract_value_usd")
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not (frame["active_contracts"] % 1 == 0).all():
        raise ValueError("active_contracts must contain integer values")
    frame["active_contracts"] = frame["active_contracts"].astype("int64")
    frame = frame.sort_values("month").reset_index(drop=True)

    if frame[list(required)].isna().any().any():
        raise ValueError("Consolidated dataset contains null values")
    if frame["month"].duplicated().any():
        raise ValueError("Consolidated dataset contains duplicate months")
    if not (frame["month"].dt.day == 1).all():
        raise ValueError("Every month must be represented by its first calendar day")
    if not (frame["revenue_usd"] > 0).all():
        raise ValueError("Revenue must be positive")
    if len(frame) != EXPECTED_MONTHS:
        raise ValueError(f"Expected {EXPECTED_MONTHS} consolidated months, got {len(frame)}")

    expected = pd.date_range(TRAIN_START, TEST_END, freq="MS")
    if not frame["month"].reset_index(drop=True).equals(pd.Series(expected, name="month")):
        raise ValueError("Consolidated months must be continuous from 2016-01 through 2025-12")
    return frame


def build_features(history: pd.DataFrame) -> pd.DataFrame:
    """Build causal calendar and income-history features.

    For every target month, lag and rolling features reference only revenue
    strictly before that month. Do not pass observed test revenues to this
    function when constructing recursive test-period features.
    """
    required = {"month", "revenue_usd"}
    if not required.issubset(history.columns):
        raise ValueError(f"history must contain {sorted(required)}")
    data = history.loc[:, ["month", "revenue_usd"]].copy()
    data["month"] = pd.to_datetime(data["month"], errors="raise")
    data["revenue_usd"] = pd.to_numeric(data["revenue_usd"], errors="raise")
    data = data.sort_values("month").reset_index(drop=True)

    month_number = data["month"].dt.month
    features = pd.DataFrame(index=data.index)
    features["year"] = data["month"].dt.year
    features["month"] = month_number
    features["quarter"] = data["month"].dt.quarter
    features["trend"] = range(len(data))
    features["month_sin"] = (2 * pd.Series(month_number, dtype="float64") * math.pi / 12).map(math.sin)
    features["month_cos"] = (2 * pd.Series(month_number, dtype="float64") * math.pi / 12).map(math.cos)

    revenue = data["revenue_usd"]
    for lag in LAGS:
        features[f"revenue_lag_{lag}"] = revenue.shift(lag)
    prior_revenue = revenue.shift(1)
    for window in ROLLING_WINDOWS:
        features[f"revenue_roll_mean_{window}"] = prior_revenue.rolling(
            window=window, min_periods=window
        ).mean()
    features["revenue_roll_std_12"] = prior_revenue.rolling(
        window=12, min_periods=12
    ).std()
    return features


def year_over_year_growth(data: pd.DataFrame) -> pd.DataFrame:
    """Return each month's revenue change versus the same month one year earlier."""
    if not {"month", "revenue_usd"}.issubset(data.columns):
        raise ValueError("data must contain month and revenue_usd")
    ordered = data.loc[:, ["month", "revenue_usd"]].copy()
    ordered["month"] = pd.to_datetime(ordered["month"], errors="raise")
    ordered["revenue_usd"] = pd.to_numeric(ordered["revenue_usd"], errors="raise")
    ordered = ordered.sort_values("month").reset_index(drop=True)
    ordered["yoy_growth_pct"] = ordered["revenue_usd"].pct_change(periods=12) * 100
    return ordered

def temporal_split(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split original monthly observations into the fixed chronological 8/2 periods."""
    if "month" not in data.columns:
        raise ValueError("data must contain a month column")
    ordered = data.sort_values("month").reset_index(drop=True)
    train = ordered.loc[ordered["month"].between(TRAIN_START, TRAIN_END)].copy()
    test = ordered.loc[ordered["month"].between(TEST_START, TEST_END)].copy()
    if len(train) != 96 or len(test) != 24:
        raise ValueError(f"Expected 96 training and 24 test months, got {len(train)} and {len(test)}")
    if train["month"].max() >= test["month"].min():
        raise ValueError("Training and test periods overlap or are out of order")
    if set(train["month"]) & set(test["month"]):
        raise ValueError("Training and test months overlap")
    return train, test


def make_recursive_features(
    target_month: str | pd.Timestamp,
    prior_revenue: Iterable[float],
    trend_index: int,
) -> pd.DataFrame:
    """Build one prediction row from past actuals plus prior predictions only.

    ``prior_revenue`` must end with the latest available historic or recursively
    predicted revenue. Test-period actuals must never be appended to it.
    """
    values = [float(value) for value in prior_revenue]
    if len(values) < 12:
        raise ValueError("At least 12 prior revenue values are required")
    month = pd.Timestamp(target_month)
    if month.day != 1:
        raise ValueError("target_month must be the first day of its month")

    row: dict[str, float | int] = {
        "year": month.year,
        "month": month.month,
        "quarter": month.quarter,
        "trend": int(trend_index),
        "month_sin": math.sin(2 * math.pi * month.month / 12),
        "month_cos": math.cos(2 * math.pi * month.month / 12),
    }
    for lag in LAGS:
        row[f"revenue_lag_{lag}"] = values[-lag]
    for window in ROLLING_WINDOWS:
        window_values = values[-window:]
        row[f"revenue_roll_mean_{window}"] = sum(window_values) / window
    window_values = values[-12:]
    mean_12 = sum(window_values) / 12
    row["revenue_roll_std_12"] = (
        sum((value - mean_12) ** 2 for value in window_values) / 11
    ) ** 0.5
    return pd.DataFrame([row])


