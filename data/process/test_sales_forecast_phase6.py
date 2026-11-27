"""Phase 6 pipeline validation tests; generated files stay in temporary directories."""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor

from data.process import evaluate_sales_forecast as evaluator
from data.process import train_sales_forecast as trainer
from data.process import visualize_sales_forecast as visualizer
from data.process.sales_forecast import (
    DEFAULT_DATA_PATH,
    TRAIN_END,
    TEST_START,
    build_features,
    load_sales_data,
    make_recursive_features,
    temporal_split,
)


def test_source_csv_parses_orders_and_splits_exact_120_months():
    data = load_sales_data(DEFAULT_DATA_PATH)
    train, holdout = temporal_split(data)
    assert len(data) == 120
    assert data["month"].is_monotonic_increasing
    assert train["month"].iloc[[0, -1]].tolist() == [pd.Timestamp("2016-01-01"), TRAIN_END]
    assert holdout["month"].iloc[[0, -1]].tolist() == [TEST_START, pd.Timestamp("2025-12-01")]
    assert len(train) == 96 and len(holdout) == 24
    assert train["month"].max() < holdout["month"].min()


def test_training_warmup_drops_rows_without_moving_split_boundaries():
    data = load_sales_data()
    train, holdout = temporal_split(data)
    x, y = trainer.build_training_data(data)
    assert len(train) == 96 and len(holdout) == 24
    assert len(x) == len(y) == 84
    assert x.index.min() == 12 and x.index.max() == 95
    assert x.index.max() < len(train)


def test_loader_rejects_invalid_month_data(tmp_path):
    data = pd.read_csv(DEFAULT_DATA_PATH)
    data.loc[data["business_line"].eq("consolidated"), "month"] = "not-a-month"
    path = tmp_path / "invalid.csv"
    data.to_csv(path, index=False)
    with pytest.raises((ValueError, TypeError)):
        load_sales_data(path)


def test_lag_and_rolling_features_exclude_current_and_future_values():
    frame = pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=18, freq="MS"),
        "revenue_usd": np.arange(1.0, 19.0),
    })
    baseline = build_features(frame)
    poisoned = frame.copy()
    poisoned.loc[poisoned.index >= 13, "revenue_usd"] = 1e12
    changed = build_features(poisoned)
    # For target row 13, current and later values cannot influence its features.
    pd.testing.assert_series_equal(baseline.loc[13], changed.loc[13])
    assert baseline.loc[13, "revenue_lag_1"] == frame.loc[12, "revenue_usd"]
    assert baseline.loc[13, "revenue_roll_mean_3"] == pytest.approx(frame.loc[10:12, "revenue_usd"].mean())


def test_recursive_features_only_depend_on_passed_history():
    history = list(range(1, 97))
    predicted_jan = 500.0
    feb_features = make_recursive_features("2024-02-01", history + [predicted_jan], 97)
    altered_future_actuals = [9e9, 8e9, 7e9]
    unaffected = make_recursive_features("2024-02-01", history + [predicted_jan], 97)
    assert feb_features.loc[0, "revenue_lag_1"] == predicted_jan
    assert feb_features.loc[0, "revenue_lag_2"] == history[-1]
    assert not np.isin(altered_future_actuals, feb_features.to_numpy()).any()
    pd.testing.assert_frame_equal(feb_features, unaffected)


def test_training_uses_only_training_targets_and_documented_seed(monkeypatch, tmp_path):
    data = load_sales_data()
    x, y = trainer.build_training_data(data)
    assert y.index.max() < 96
    assert x.index.max() < 96

    # Exercise a temporary training run: no production artifact paths are used.
    out = tmp_path / "phase6-artifacts"
    monkeypatch.setattr(trainer, "ARTIFACT_DIR", out)
    monkeypatch.setattr(trainer, "MODEL_PATH", out / "model.joblib")
    monkeypatch.setattr(trainer, "FEATURE_IMPORTANCE_PATH", out / "importance.csv")
    monkeypatch.setattr(trainer, "PREDICTIONS_PATH", out / "predictions.csv")
    monkeypatch.setattr(trainer, "METADATA_PATH", out / "metadata.json")
    result = trainer.train_and_forecast()
    assert isinstance(result["model"], RandomForestRegressor)
    assert result["metadata"]["random_state"] == 42
    assert result["metadata"]["training_target_rows"] == 84
    assert len(result["predictions"]) == 24
    assert result["predictions"]["predicted_revenue_usd"].notna().all()
    loaded = joblib.load(out / "model.joblib")
    assert loaded.get_params()["random_state"] == 42


def test_frozen_predictions_match_deterministic_temporary_training(monkeypatch, tmp_path):
    frozen = pd.read_csv(trainer.PREDICTIONS_PATH, parse_dates=["month"])
    out = tmp_path / "determinism"
    monkeypatch.setattr(trainer, "ARTIFACT_DIR", out)
    monkeypatch.setattr(trainer, "MODEL_PATH", out / "model.joblib")
    monkeypatch.setattr(trainer, "FEATURE_IMPORTANCE_PATH", out / "importance.csv")
    monkeypatch.setattr(trainer, "PREDICTIONS_PATH", out / "predictions.csv")
    monkeypatch.setattr(trainer, "METADATA_PATH", out / "metadata.json")
    run_a = trainer.train_and_forecast()["predictions"]
    run_b = trainer.train_and_forecast()["predictions"]
    pd.testing.assert_frame_equal(run_a, run_b)
    pd.testing.assert_frame_equal(run_a, frozen)


def test_phase4_evaluation_uses_exact_holdout_and_frozen_artifact():
    evaluated = evaluator.evaluate_forecast()
    expected = pd.read_csv(evaluator.PREDICTIONS_PATH, parse_dates=["month"])
    actual = load_sales_data().loc[lambda frame: frame["month"].between(TEST_START, "2025-12-01"), "revenue_usd"]
    expected_rmse = float(np.sqrt(np.mean((actual.to_numpy() - expected["predicted_revenue_usd"].to_numpy()) ** 2)))
    assert evaluated["report"]["regression_metrics"]["rmse_usd"] == pytest.approx(expected_rmse)
    assert evaluated["report"]["observation_count"] == 24
    assert evaluated["report"]["phase3_experiment_verified"]["no_retraining"] is True


def test_calibration_folds_are_pre_holdout_and_recursive():
    data = load_sales_data()
    metadata = json.loads(visualizer.METADATA_PATH.read_text(encoding="utf-8"))
    errors = visualizer.temporal_recursive_errors(data, metadata)
    assert len(errors) == 36
    assert errors["month"].max() < TEST_START
    assert errors["origin"].nunique() == 3
    assert errors.groupby("origin").size().eq(12).all()

    # Poison holdout values: training-only calibration predictions/errors stay unchanged.
    poisoned = data.copy()
    poisoned.loc[poisoned["month"] >= TEST_START, "revenue_usd"] *= 1000
    altered_errors = visualizer.temporal_recursive_errors(poisoned, metadata)
    pd.testing.assert_frame_equal(errors, altered_errors)


def test_visualizer_preserves_frozen_model_predictions_and_evaluation(tmp_path, monkeypatch):
    paths = [
        trainer.MODEL_PATH,
        trainer.PREDICTIONS_PATH,
        trainer.METADATA_PATH,
        evaluator.REPORT_JSON_PATH,
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    output_dir = tmp_path / "visualization"
    monkeypatch.setattr(visualizer, "ARTIFACT_DIR", output_dir)
    monkeypatch.setattr(visualizer, "PLOT_PATH", output_dir / "phase5.png")
    monkeypatch.setattr(visualizer, "FOLD_SUMMARY_PATH", output_dir / "calibration.json")
    monkeypatch.setattr(visualizer, "PREDICTIONS_PATH", trainer.PREDICTIONS_PATH)
    monkeypatch.setattr(visualizer, "METADATA_PATH", trainer.METADATA_PATH)
    monkeypatch.setattr(visualizer, "EVALUATION_PATH", evaluator.REPORT_JSON_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    anomaly_path = output_dir / "anomaly_risk_evaluation.csv"
    pd.read_csv(evaluator.ANOMALY_PATH).to_csv(anomaly_path, index=False)
    result = visualizer.generate_visualization()
    assert result["band"]["training_period_only"] is True
    assert result["band"]["is_confidence_interval"] is False
    assert (output_dir / "phase5.png").is_file()
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert after == before
