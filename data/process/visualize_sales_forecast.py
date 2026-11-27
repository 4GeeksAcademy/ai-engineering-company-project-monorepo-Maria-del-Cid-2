"""Create a Phase 5 plot from the frozen Nexova forecast and train-only calibration folds.

Run from the repository root with:
    python -m data.process.visualize_sales_forecast
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .evaluate_sales_forecast import ARTIFACT_DIR
from .sales_forecast import (
    DEFAULT_DATA_PATH,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    load_sales_data,
    make_recursive_features,
    temporal_split,
)
from .train_sales_forecast import FEATURE_COLUMNS

PREDICTIONS_PATH = ARTIFACT_DIR / "sales_forecast_predictions.csv"
METADATA_PATH = ARTIFACT_DIR / "training_metadata.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation_report.json"
PLOT_PATH = ARTIFACT_DIR / "sales_forecast_phase5.png"
FOLD_SUMMARY_PATH = ARTIFACT_DIR / "forecast_variability_calibration.json"

# Expanding-window origins use only 2016-2023 observations. Each fold fits the
# same declared model and rolls predictions recursively for a 12-month horizon.
FOLD_ORIGINS = (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01"), pd.Timestamp("2022-01-01"))
CALIBRATION_HORIZON_MONTHS = 12
BAND_QUANTILE = 0.90


def _fit_recreate_model(metadata: dict) -> RandomForestRegressor:
    """Fit the training-period recipe from metadata for historical calibration only."""
    params = dict(metadata["hyperparameters"])
    params["n_jobs"] = 1  # deterministic, modest resource use; does not alter fitted values
    return RandomForestRegressor(**params)


def temporal_recursive_errors(data: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    """Generate expanding-window recursive validation errors, entirely pre-holdout."""
    rows: list[dict[str, object]] = []
    for origin in FOLD_ORIGINS:
        history = data.loc[data["month"] < origin].copy().reset_index(drop=True)
        targets = data.loc[
            data["month"].between(origin, origin + pd.DateOffset(months=CALIBRATION_HORIZON_MONTHS - 1))
        ].reset_index(drop=True)
        if len(targets) != CALIBRATION_HORIZON_MONTHS or history["month"].max() >= origin:
            raise ValueError(f"Invalid temporal calibration fold at {origin:%Y-%m}")
        model = _fit_recreate_model(metadata)
        # Recreate Phase 3's supervised training rows and 12-month feature warmup.
        from .sales_forecast import build_features
        feature_frame = build_features(history)
        train_mask = history["month"].between(TRAIN_START, history["month"].max())
        x = feature_frame.loc[train_mask, FEATURE_COLUMNS]
        y = history.loc[train_mask, "revenue_usd"]
        usable = x.notna().all(axis=1)
        x, y = x.loc[usable], y.loc[usable]
        if x.empty:
            raise ValueError(f"No training rows for calibration origin {origin:%Y-%m}")
        model.fit(x, y)
        recursive_history = history["revenue_usd"].astype(float).tolist()
        for target in targets.itertuples(index=False):
            feature_row = make_recursive_features(target.month, recursive_history, len(recursive_history))
            predicted = float(model.predict(feature_row.loc[:, FEATURE_COLUMNS])[0])
            actual = float(target.revenue_usd)
            rows.append({
                "origin": origin,
                "month": target.month,
                "horizon_month": int((target.month.year - origin.year) * 12 + target.month.month - origin.month + 1),
                "actual_revenue_usd": actual,
                "predicted_revenue_usd": predicted,
                "absolute_error_usd": abs(actual - predicted),
                "residual_usd": actual - predicted,
            })
            recursive_history.append(predicted)
    return pd.DataFrame(rows)


def calculate_variability_band(errors: pd.DataFrame) -> dict[str, float | int | str]:
    """Estimate one symmetric descriptive residual band from recursive validation errors.

    The half-width is the empirical 90th percentile of absolute residuals at
    forecast horizons 1-12, pooled across three expanding-window folds.
    """
    selected = errors.loc[errors["horizon_month"].between(1, CALIBRATION_HORIZON_MONTHS), "absolute_error_usd"]
    values = pd.to_numeric(selected, errors="raise").to_numpy(dtype=float)
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Finite recursive validation errors are required to estimate the band")
    return {
        "method": "pooled empirical quantile of absolute recursive validation residuals",
        "quantile": BAND_QUANTILE,
        "half_width_usd": float(np.quantile(values, BAND_QUANTILE)),
        "validation_origins": len(FOLD_ORIGINS),
        "fold_count": len(FOLD_ORIGINS),
        "errors_used": int(len(values)),
        "horizon_months": CALIBRATION_HORIZON_MONTHS,
        "training_period_only": True,
        "is_confidence_interval": False,
    }


def generate_visualization() -> dict[str, object]:
    """Create a PNG visualization without modifying model or forecast artifacts."""
    data = load_sales_data(DEFAULT_DATA_PATH)
    train, test = temporal_split(data)
    predictions = pd.read_csv(PREDICTIONS_PATH, parse_dates=["month"])
    if not predictions["month"].equals(test["month"].reset_index(drop=True)):
        raise ValueError("Frozen prediction dates must exactly match the 24 holdout months")
    if predictions["predicted_revenue_usd"].isna().any() or not np.isfinite(predictions["predicted_revenue_usd"]).all():
        raise ValueError("Frozen prediction values must be finite")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    report = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    calibration_errors = temporal_recursive_errors(data, metadata)
    band = calculate_variability_band(calibration_errors)
    half_width = float(band["half_width_usd"])
    actual = test["revenue_usd"].to_numpy(dtype=float)
    predicted = predictions["predicted_revenue_usd"].to_numpy(dtype=float)
    residuals = actual - predicted

    # Follow Phase 4's existing business anomaly labels. Separately mark only
    # deviations outside the training-only descriptive variability band.
    anomaly_rows = pd.read_csv(ARTIFACT_DIR / "anomaly_risk_evaluation.csv", parse_dates=["month"])
    if not anomaly_rows["month"].equals(test["month"].reset_index(drop=True)):
        raise ValueError("Phase 4 anomaly labels must match holdout months exactly")
    deviations = np.abs(residuals) > half_width
    evaluation = report["regression_metrics"]
    k2 = report["k2_score"]["value"]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(13, 7.2), layout="constrained")
    ax.fill_between(
        test["month"], predicted - half_width, predicted + half_width,
        color="#4C78A8", alpha=0.17,
        label=f"Banda orientativa de variabilidad (±${half_width:,.0f})",
    )
    ax.plot(test["month"], predicted, color="#286090", marker="o", linewidth=2.2,
            markersize=4.5, label="Ingresos predichos (forecast congelado)")
    ax.plot(test["month"], actual, color="#222222", marker="o", linewidth=2.0,
            markersize=4.5, label="Ingresos reales")
    ax.scatter(test.loc[deviations, "month"], actual[deviations], marker="D", s=76,
               color="#D62728", edgecolor="white", linewidth=0.8, zorder=5,
               label="Real fuera de banda orientativa")
    # The Phase 4 anomaly criterion denotes a separate business-oriented label.
    business_anomalies = anomaly_rows["anomaly_label"].astype(bool).to_numpy()
    ax.scatter(test.loc[business_anomalies, "month"], actual[business_anomalies],
               marker="x", s=92, color="#7A3E9D", linewidth=2.2, zorder=6,
               label="Etiqueta de anomalía Fase 4 (YoY)")

    ax.set_title("Ingresos Nexova: valores reales y predicción congelada\nHoldout mensual 2024–2025", fontsize=16, weight="bold")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Ingresos (USD)")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"${value:,.0f}"))
    ax.margins(x=0.02)
    ax.legend(loc="best", frameon=True, fontsize=9)
    ax.text(
        0.01, 0.985,
        f"Real total: ${actual.sum():,.0f}   |   Predicho: ${predicted.sum():,.0f}   |   Diferencia: ${actual.sum()-predicted.sum():+,.0f}\n"
        f"RMSE: ${evaluation['rmse_usd']:,.0f}   |   K2 (RMSSE): {k2:.3f} (>1: no supera baseline estacional)",
        transform=ax.transAxes, va="top", ha="left", fontsize=9,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
    )
    fig.text(0.01, 0.005,
             "La banda es descriptiva, calibrada con folds recursivos de entrenamiento; no es intervalo de confianza ni garantía futura. "
             "Desviación fuera de banda ≠ anomalía de negocio confirmada.", fontsize=8, color="#444444")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_PATH, dpi=180, facecolor="white")
    plt.close(fig)

    calibration_errors.to_csv(ARTIFACT_DIR / "forecast_variability_calibration.csv", index=False, date_format="%Y-%m-%d")
    FOLD_SUMMARY_PATH.write_text(json.dumps({"band": band, "deviations_outside_band": int(deviations.sum()),
                                                "phase4_anomaly_labels": int(business_anomalies.sum()),
                                                "holdout_period": {"start": str(TEST_START.date()), "end": str(TEST_END.date())}},
                                               indent=2, allow_nan=False), encoding="utf-8")
    return {"plot_path": str(PLOT_PATH), "band": band,
            "deviation_months": [str(value.date()) for value in test.loc[deviations, "month"]],
            "phase4_anomaly_months": [str(value.date()) for value in test.loc[business_anomalies, "month"]],
            "actual_total_usd": float(actual.sum()), "predicted_total_usd": float(predicted.sum()),
            "difference_usd": float(actual.sum() - predicted.sum()),
            "rmse_usd": float(evaluation["rmse_usd"]), "k2": float(k2)}


if __name__ == "__main__":
    print(json.dumps(generate_visualization(), indent=2, ensure_ascii=False))
