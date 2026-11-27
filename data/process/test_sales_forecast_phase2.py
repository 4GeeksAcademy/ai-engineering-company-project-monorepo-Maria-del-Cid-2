"""Focused validation for Phase 2 data preparation; no model training."""

import pandas as pd
import pytest

from data.process.sales_forecast import (
    DEFAULT_DATA_PATH,
    build_features,
    load_sales_data,
    make_recursive_features,
    temporal_split,
    year_over_year_growth,
)


def test_dataset_and_fixed_chronological_split():
    data = load_sales_data(DEFAULT_DATA_PATH)
    train, test = temporal_split(data)
    assert len(data) == 120
    assert len(train) == 96
    assert len(test) == 24
    assert train["month"].min() == pd.Timestamp("2016-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")
    assert test["month"].min() == pd.Timestamp("2024-01-01")
    assert test["month"].max() == pd.Timestamp("2025-12-01")
    assert set(train["month"]).isdisjoint(set(test["month"]))
    assert train["month"].is_unique and test["month"].is_unique


def test_features_are_causal_and_exclude_future_business_values():
    data = load_sales_data()
    features = build_features(data)
    expected = {
        "year", "month", "quarter", "trend", "month_sin", "month_cos",
        "revenue_lag_1", "revenue_lag_2", "revenue_lag_3",
        "revenue_lag_6", "revenue_lag_12", "revenue_roll_mean_3",
        "revenue_roll_mean_6", "revenue_roll_mean_12", "revenue_roll_std_12",
    }
    assert set(features.columns) == expected
    assert not {"revenue_usd", "active_contracts", "avg_contract_value_usd"} & set(features.columns)
    # At the Jan-2024 feature row, all history-derived fields are based on 2023 or earlier.
    index = data.index[data["month"].eq(pd.Timestamp("2024-01-01"))][0]
    assert features.loc[index, "revenue_lag_1"] == data.loc[index - 1, "revenue_usd"]
    assert features.loc[index, "revenue_lag_12"] == data.loc[index - 12, "revenue_usd"]
    assert features.loc[index, "revenue_roll_mean_3"] == data.loc[index - 3:index - 1, "revenue_usd"].mean()
    assert features.loc[index, "revenue_roll_mean_12"] == pytest.approx(data.loc[index - 12:index - 1, "revenue_usd"].mean())


def test_recursive_features_use_only_supplied_history():
    data = load_sales_data()
    train, test = temporal_split(data)
    history = train["revenue_usd"].tolist()
    first_features = make_recursive_features(test.iloc[0]["month"], history, 96)
    first_predicted_value = 999_999.0
    second_features = make_recursive_features(test.iloc[1]["month"], history + [first_predicted_value], 97)
    assert second_features.loc[0, "revenue_lag_1"] == first_predicted_value
    assert second_features.loc[0, "revenue_lag_2"] == history[-1]
    assert first_features.loc[0, "revenue_lag_1"] == history[-1]
    # Changed test actuals are not passed to the recursive helper and cannot affect its output.
    altered_test_actual = float(test.iloc[0]["revenue_usd"]) + 123_456.0
    unaffected = make_recursive_features(test.iloc[1]["month"], history + [first_predicted_value], 97)
    assert altered_test_actual not in unaffected.to_numpy()


def test_monthly_yoy_growth_is_computed_for_matching_months():
    data = load_sales_data()
    growth = year_over_year_growth(data)
    row = growth.loc[growth["month"].eq(pd.Timestamp("2024-01-01"))].iloc[0]
    prior = data.loc[data["month"].eq(pd.Timestamp("2023-01-01")), "revenue_usd"].iloc[0]
    actual = data.loc[data["month"].eq(pd.Timestamp("2024-01-01")), "revenue_usd"].iloc[0]
    assert abs(row["yoy_growth_pct"] - (actual / prior - 1) * 100) < 1e-10


