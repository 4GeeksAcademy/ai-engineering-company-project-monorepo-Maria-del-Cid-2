"""Train and persist the Phase 3 Nexova recursive sales forecast."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .sales_forecast import (
    DEFAULT_DATA_PATH,
    build_features,
    load_sales_data,
    make_recursive_features,
    temporal_split,
)

PROCESS_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PROCESS_DIR / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "sales_random_forest.joblib"
FEATURE_IMPORTANCE_PATH = ARTIFACT_DIR / "feature_importance.csv"
PREDICTIONS_PATH = ARTIFACT_DIR / "sales_forecast_predictions.csv"
METADATA_PATH = ARTIFACT_DIR / "training_metadata.json"
FEATURE_COLUMNS = [
    "year", "month", "quarter", "trend", "month_sin", "month_cos",
    "revenue_lag_1", "revenue_lag_2", "revenue_lag_3", "revenue_lag_6",
    "revenue_lag_12", "revenue_roll_mean_3", "revenue_roll_mean_6",
    "revenue_roll_mean_12", "revenue_roll_std_12",
]


def build_training_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Create training X/y using only 2016â€“2023 target rows."""
    train, _ = temporal_split(data)
    all_features = build_features(data)
    mask = data["month"].between("2016-01-01", "2023-12-01")
    x = all_features.loc[mask, FEATURE_COLUMNS]
    y = data.loc[mask, "revenue_usd"]
    usable = x.notna().all(axis=1)
    x, y = x.loc[usable], y.loc[usable]
    if x.empty or x.index.max() >= len(train):
        raise ValueError("Training features escaped the 2016â€“2023 target period")
    if len(x) != 84:
        raise ValueError(f"Expected 84 train rows with 12 months of warm-up, got {len(x)}")
    if x.index.max() != 95 or len(y) != len(x):
        raise ValueError("Training feature/target period alignment failed")
    return x, y


def train_and_forecast(data_path: str | Path = DEFAULT_DATA_PATH) -> dict[str, object]:
    """Fit the fixed Random Forest, recursively forecast all 24 test months, save artifacts."""
    data = load_sales_data(data_path)
    train, test = temporal_split(data)
    x_train, y_train = build_training_data(data)

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=5,
        min_samples_split=4,
        min_samples_leaf=2,
        max_features=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    history = train["revenue_usd"].astype(float).tolist()
    prediction_rows: list[dict[str, object]] = []
    for target_month in test["month"]:
        features = make_recursive_features(
            target_month=target_month,
            prior_revenue=history,
            trend_index=len(history),
        ).loc[:, FEATURE_COLUMNS]
        prediction = float(model.predict(features)[0])
        if not pd.notna(prediction) or prediction <= 0:
            raise ValueError(f"Model generated an invalid prediction for {target_month}")
        prediction_rows.append({"month": target_month, "predicted_revenue_usd": prediction})
        history.append(prediction)

    predictions = pd.DataFrame(prediction_rows)
    if len(predictions) != 24 or predictions["month"].duplicated().any():
        raise ValueError("Recursive forecast must contain exactly 24 unique months")
    if not predictions["month"].equals(test["month"].reset_index(drop=True)):
        raise ValueError("Recursive prediction months do not match the holdout period")

    importances = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False, ignore_index=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    importances.to_csv(FEATURE_IMPORTANCE_PATH, index=False)
    predictions.to_csv(PREDICTIONS_PATH, index=False, date_format="%Y-%m-%d")
    metadata = {
        "algorithm": "sklearn.ensemble.RandomForestRegressor",
        "random_state": 42,
        "training_period": {"start": "2016-01-01", "end": "2023-12-01"},
        "training_target_rows": int(len(y_train)),
        "training_rows_with_warmup": int(len(train)),
        "test_period": {"start": "2024-01-01", "end": "2025-12-01"},
        "recursive_prediction_count": int(len(predictions)),
        "feature_columns": FEATURE_COLUMNS,
        "hyperparameters": model.get_params(),
        "note": "No test actuals were used for fitting or recursive feature history.",
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "model": model,
        "x_train": x_train,
        "y_train": y_train,
        "predictions": predictions,
        "feature_importance": importances,
        "metadata": metadata,
        "paths": {
            "model": MODEL_PATH,
            "predictions": PREDICTIONS_PATH,
            "feature_importance": FEATURE_IMPORTANCE_PATH,
            "metadata": METADATA_PATH,
        },
    }


if __name__ == "__main__":
    result = train_and_forecast()
    print(f"Trained on {len(result['y_train'])} target rows; produced {len(result['predictions'])} recursive predictions.")
    print(result["feature_importance"].to_string(index=False))
    print("Artifacts:")
    for artifact, path in result["paths"].items():
        print(f"  {artifact}: {path}")

