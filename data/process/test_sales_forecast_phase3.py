"""Tests for bounded Random Forest training and recursive forecast artifacts."""

import json

import pandas as pd
import pytest

from data.process import train_sales_forecast as pipeline
from data.process.sales_forecast import load_sales_data


def test_training_data_uses_only_2016_to_2023_targets():
    data = load_sales_data()
    x_train, y_train = pipeline.build_training_data(data)
    assert len(x_train) == len(y_train) == 84
    assert x_train.index.min() == 12
    assert x_train.index.max() == 95
    assert x_train.index.max() < 96


def test_recursive_forecast_artifacts_and_seeded_model(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setattr(pipeline, "ARTIFACT_DIR", artifact_dir)
    monkeypatch.setattr(pipeline, "MODEL_PATH", artifact_dir / "model.joblib")
    monkeypatch.setattr(pipeline, "FEATURE_IMPORTANCE_PATH", artifact_dir / "importance.csv")
    monkeypatch.setattr(pipeline, "PREDICTIONS_PATH", artifact_dir / "predictions.csv")
    monkeypatch.setattr(pipeline, "METADATA_PATH", artifact_dir / "metadata.json")

    result = pipeline.train_and_forecast()
    predictions = result["predictions"]
    assert len(predictions) == 24
    assert predictions["month"].iloc[0] == pd.Timestamp("2024-01-01")
    assert predictions["month"].iloc[-1] == pd.Timestamp("2025-12-01")
    assert predictions["predicted_revenue_usd"].notna().all()
    assert result["metadata"]["training_target_rows"] == 84
    assert result["metadata"]["random_state"] == 42
    assert result["metadata"]["hyperparameters"]["random_state"] == 42
    assert result["feature_importance"]["importance"].sum() == pytest.approx(1.0)
    assert all(path.is_file() for path in result["paths"].values())

    saved_predictions = pd.read_csv(result["paths"]["predictions"])
    assert len(saved_predictions) == 24
    assert saved_predictions["month"].iloc[0] == "2024-01-01"
    metadata = json.loads(result["paths"]["metadata"].read_text(encoding="utf-8"))
    assert metadata["note"].startswith("No test actuals")


def test_test_actual_changes_cannot_change_recursive_forecast(tmp_path, monkeypatch):
    data = load_sales_data()
    altered = data.copy()
    altered.loc[altered["month"] >= "2024-01-01", "revenue_usd"] *= 9
    path = tmp_path / "altered_test_actuals.csv"
    altered.to_csv(path, index=False)

    # Isolate outputs so this determinism/leakage check doesn't overwrite the standard artifacts.
    isolated = tmp_path / "isolated"
    monkeypatch.setattr(pipeline, "ARTIFACT_DIR", isolated)
    monkeypatch.setattr(pipeline, "MODEL_PATH", isolated / "model.joblib")
    monkeypatch.setattr(pipeline, "FEATURE_IMPORTANCE_PATH", isolated / "importance.csv")
    monkeypatch.setattr(pipeline, "PREDICTIONS_PATH", isolated / "predictions.csv")
    monkeypatch.setattr(pipeline, "METADATA_PATH", isolated / "metadata.json")
    baseline = pipeline.train_and_forecast()
    changed = pipeline.train_and_forecast(path)
    pd.testing.assert_frame_equal(baseline["predictions"], changed["predictions"])

