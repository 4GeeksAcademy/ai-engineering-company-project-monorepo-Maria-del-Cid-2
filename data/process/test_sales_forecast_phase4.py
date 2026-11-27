"""Unit tests for the isolated Phase 4 evaluator."""

import numpy as np
import pandas as pd
import pytest

from data.process.evaluate_sales_forecast import (
    anomaly_gini, calculate_psi, calculate_k2_rmsse, evaluate_forecast, regression_metrics,
)


def test_regression_metrics_hand_calculation():
    result = regression_metrics(pd.Series([10.0, 20.0]), pd.Series([12.0, 18.0]))
    assert result["mse_usd_squared"] == pytest.approx(4.0)
    assert result["rmse_usd"] == pytest.approx(2.0)
    assert result["mean_actual_revenue_usd"] == pytest.approx(15.0)
    assert result["rmse_pct_of_mean_actual"] == pytest.approx(200 / 15)


def test_psi_identical_distributions_is_zero_and_infinite_edges_cover_extremes():
    values = pd.Series(np.arange(1, 101, dtype=float))
    result = calculate_psi(values, values.copy())
    assert result["psi"] == pytest.approx(0.0)
    assert result["bin_edges"][0] == -float("inf")
    assert result["bin_edges"][-1] == float("inf")


def test_psi_handles_ties_and_empty_comparison_bins():
    ref = pd.Series([1.0] * 20 + [2.0] * 20)
    comp = pd.Series([2.0] * 8 + [1000.0] * 2)
    result = calculate_psi(ref, comp)
    assert np.isfinite(result["psi"])
    assert sum(result["reference_proportions"]) == pytest.approx(1.0)
    assert sum(result["comparison_proportions"]) == pytest.approx(1.0)


def test_anomaly_gini_returns_undefined_for_single_class():
    months = pd.date_range("2016-01-01", "2023-12-01", freq="MS")
    train = pd.DataFrame({"month": months, "revenue_usd": np.full(len(months), 100.0)})
    test_months = pd.date_range("2024-01-01", periods=24, freq="MS")
    test = pd.DataFrame({"month": test_months, "revenue_usd": np.full(24, 100.0)})
    pred = pd.DataFrame({"month": test_months, "predicted_revenue_usd": np.full(24, 100.0)})
    result = anomaly_gini(train, test, pred)
    assert result["status"] == "undefined_single_class"
    assert result["roc_auc"] is None
    assert result["gini"] is None


def test_evaluation_uses_frozen_predictions_and_exact_dates():
    result = evaluate_forecast()
    report = result["report"]
    assert report["observation_count"] == 24
    assert report["phase3_experiment_verified"]["no_retraining"] is True
    assert report["anomaly_gini"]["observation_count"] == 24
    assert report["k2_score"]["status"] == "valid"
    assert report["k2_score"]["training_seasonal_differences"] == 84
    assert "revenue_lag_1" in {row["feature"] for row in report["psi"]["variables"]}


def test_prediction_dates_must_match_exactly(tmp_path):
    from data.process.evaluate_sales_forecast import PREDICTIONS_PATH

    original = pd.read_csv(PREDICTIONS_PATH, parse_dates=["month"])
    original.loc[0, "month"] = original.loc[0, "month"] + pd.DateOffset(months=1)
    bad_path = tmp_path / "bad_predictions.csv"
    original.to_csv(bad_path, index=False)
    with pytest.raises(ValueError, match="dates must match"):
        evaluate_forecast(predictions_path=bad_path)




def test_k2_rmsse_hand_calculation_and_training_only_denominator():
    train = np.arange(1.0, 25.0)
    actual = np.array([10.0, 20.0])
    pred = np.array([12.0, 18.0])
    result = calculate_k2_rmsse(train, actual, pred, seasonal_period=12)
    expected_denominator = np.mean((train[12:] - train[:-12]) ** 2)
    assert result["numerator_test_mse"] == pytest.approx(4.0)
    assert result["denominator_training_seasonal_naive_mse"] == pytest.approx(expected_denominator)
    assert result["value"] == pytest.approx(np.sqrt(4.0 / expected_denominator))
    changed_test = calculate_k2_rmsse(train, actual + 1000, pred, seasonal_period=12)
    assert changed_test["denominator_training_seasonal_naive_mse"] == pytest.approx(expected_denominator)


def test_k2_rmsse_rejects_zero_denominator_and_invalid_inputs():
    with pytest.raises(ValueError, match="is zero"):
        calculate_k2_rmsse(np.ones(24), [2.0], [1.0])
    with pytest.raises(ValueError, match="finite"):
        calculate_k2_rmsse(np.arange(24.0), [np.nan], [1.0])
    with pytest.raises(ValueError, match="equal"):
        calculate_k2_rmsse(np.arange(24.0), [2.0, 3.0], [1.0])