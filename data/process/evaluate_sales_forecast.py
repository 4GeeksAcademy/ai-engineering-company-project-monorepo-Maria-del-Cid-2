"""Phase 4 evaluation for the frozen Nexova Phase 3 forecast artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .sales_forecast import (
    DEFAULT_DATA_PATH,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    build_features,
    load_sales_data,
    temporal_split,
)
from .train_sales_forecast import FEATURE_COLUMNS

PROCESS_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PROCESS_DIR / "artifacts"
PREDICTIONS_PATH = ARTIFACT_DIR / "sales_forecast_predictions.csv"
REPORT_JSON_PATH = ARTIFACT_DIR / "evaluation_report.json"
REPORT_MD_PATH = ARTIFACT_DIR / "evaluation_report.md"
PSI_PATH = ARTIFACT_DIR / "psi_by_feature.csv"
ANOMALY_PATH = ARTIFACT_DIR / "anomaly_risk_evaluation.csv"
METADATA_PATH = ARTIFACT_DIR / "training_metadata.json"

# PSI convention: quantile edges estimated only from train; 10 bins, collapsed
# if repeated values make an edge non-unique. Infinite outer edges retain extremes.
PSI_BIN_COUNT = 10
PSI_EPSILON = 1e-6
ANOMALY_TAIL_QUANTILE = 0.10


def regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """Return test-period MSE, RMSE, real mean revenue, and normalized RMSE (%)."""
    y_true = pd.to_numeric(actual, errors="raise").to_numpy(dtype=float)
    y_pred = pd.to_numeric(predicted, errors="raise").to_numpy(dtype=float)
    if len(y_true) == 0 or len(y_true) != len(y_pred):
        raise ValueError("actual and predicted must have equal, nonzero lengths")
    if not np.isfinite(y_true).all() or not np.isfinite(y_pred).all():
        raise ValueError("actual and predicted values must be finite")
    mse = float(np.mean((y_true - y_pred) ** 2))
    rmse = float(np.sqrt(mse))
    mean_actual = float(np.mean(y_true))
    if mean_actual == 0:
        raise ValueError("mean actual revenue must be nonzero for RMSE percentage")
    return {
        "mse_usd_squared": mse,
        "rmse_usd": rmse,
        "mean_actual_revenue_usd": mean_actual,
        "rmse_pct_of_mean_actual": rmse / mean_actual * 100,
    }


def calculate_psi(
    reference: pd.Series,
    comparison: pd.Series,
    bins: int = PSI_BIN_COUNT,
    epsilon: float = PSI_EPSILON,
) -> dict[str, Any]:
    """Calculate PSI using train-reference quantile bins and a small proportion floor."""
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy(dtype=float)
    comp = pd.to_numeric(comparison, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(ref) or not len(comp):
        raise ValueError("PSI requires at least one non-null value in each period")
    if not np.isfinite(ref).all() or not np.isfinite(comp).all():
        raise ValueError("PSI values must be finite")
    if bins < 2 or not 0 < epsilon < 0.5:
        raise ValueError("bins must be >= 2 and epsilon must be between 0 and 0.5")

    quantiles = np.linspace(0, 1, bins + 1)
    inner = np.unique(np.quantile(ref, quantiles[1:-1]))
    edges = np.concatenate(([-np.inf], inner, [np.inf]))
    ref_counts, _ = np.histogram(ref, bins=edges)
    comp_counts, _ = np.histogram(comp, bins=edges)
    ref_prop = ref_counts / len(ref)
    comp_prop = comp_counts / len(comp)
    # Flooring plus renormalizing avoids zero proportions/log(0), including empty bins.
    ref_safe = np.maximum(ref_prop, epsilon)
    comp_safe = np.maximum(comp_prop, epsilon)
    ref_safe /= ref_safe.sum()
    comp_safe /= comp_safe.sum()
    psi = float(np.sum((comp_safe - ref_safe) * np.log(comp_safe / ref_safe)))
    return {
        "psi": psi,
        "reference_non_null": int(len(ref)),
        "comparison_non_null": int(len(comp)),
        "bin_edges": [float(value) for value in edges],
        "reference_proportions": ref_safe.tolist(),
        "comparison_proportions": comp_safe.tolist(),
    }


def calculate_k2_rmsse(train_actual: pd.Series | np.ndarray, test_actual: pd.Series | np.ndarray,
                       predicted: pd.Series | np.ndarray, seasonal_period: int = 12) -> dict[str, Any]:
    """Calculate Nexova K2 as RMSSE, scaling only against training seasonal-naive error."""
    train = pd.to_numeric(pd.Series(train_actual), errors="raise").to_numpy(dtype=float)
    actual = pd.to_numeric(pd.Series(test_actual), errors="raise").to_numpy(dtype=float)
    forecast = pd.to_numeric(pd.Series(predicted), errors="raise").to_numpy(dtype=float)
    if not isinstance(seasonal_period, int) or seasonal_period < 1:
        raise ValueError("seasonal_period must be a positive integer")
    if len(train) <= seasonal_period:
        raise ValueError("training data must contain more observations than seasonal_period")
    if len(actual) == 0 or len(actual) != len(forecast):
        raise ValueError("test actual and predicted must have equal, nonzero lengths")
    if not np.isfinite(train).all() or not np.isfinite(actual).all() or not np.isfinite(forecast).all():
        raise ValueError("K2 input values must be finite")
    numerator = float(np.mean((actual - forecast) ** 2))
    differences = train[seasonal_period:] - train[:-seasonal_period]
    denominator = float(np.mean(differences ** 2))
    if denominator == 0:
        raise ValueError("K2 seasonal-naive training MSE is zero; RMSSE is undefined")
    return {"value": float(np.sqrt(numerator / denominator)), "numerator_test_mse": numerator,
            "denominator_training_seasonal_naive_mse": denominator,
            "training_seasonal_differences": int(len(differences)),
            "seasonal_period_months": seasonal_period, "status": "valid"}

def anomaly_gini(
    train: pd.DataFrame,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    tail_quantile: float = ANOMALY_TAIL_QUANTILE,
) -> dict[str, Any]:
    """Rank downside risk and score true anomalous YoY drops against train-only seasonal thresholds.

    A positive label means actual same-calendar-month revenue growth is below
    that calendar month's lower-tail training cutoff. Risk is the negative of
    predicted same-month YoY growth, so higher risk means a worse forecasted
    revenue decline. Thresholds use only training actuals; scores use only
    information available at forecast time (recursive prediction / prior-year
    history), never test actuals or forecast errors.
    """
    if not 0 < tail_quantile < 0.5:
        raise ValueError("tail_quantile must be between 0 and 0.5")
    history = train.loc[:, ["month", "revenue_usd"]].copy()
    history["month"] = pd.to_datetime(history["month"])
    history["yoy_growth"] = history["revenue_usd"].pct_change(12)
    thresholds: dict[int, float] = {}
    for month_number in range(1, 13):
        values = history.loc[history["month"].dt.month.eq(month_number), "yoy_growth"].dropna()
        if values.empty:
            raise ValueError(f"Insufficient training YoY history for calendar month {month_number}")
        thresholds[month_number] = float(values.quantile(tail_quantile))

    actual_by_month = test.set_index("month")["revenue_usd"]
    prediction_by_month = predictions.set_index("month")["predicted_revenue_usd"]
    prior_actual_by_month = train.set_index("month")["revenue_usd"]
    prior_prediction: dict[pd.Timestamp, float] = {}
    pred_history = train["revenue_usd"].astype(float).tolist()
    for month, value in prediction_by_month.items():
        month = pd.Timestamp(month)
        pred_history.append(float(value))
        if month - pd.DateOffset(months=12) in prior_actual_by_month.index:
            prior_value = float(prior_actual_by_month.loc[month - pd.DateOffset(months=12)])
        else:
            prior_value = float(prediction_by_month.loc[month - pd.DateOffset(months=12)])
        prior_prediction[month] = float(value) / prior_value - 1.0

    rows = []
    for month in pd.DatetimeIndex(prediction_by_month.index):
        month = pd.Timestamp(month)
        prior_month = month - pd.DateOffset(months=12)
        prior_actual = float(
            prior_actual_by_month.loc[prior_month]
            if prior_month in prior_actual_by_month.index
            else actual_by_month.loc[prior_month]
        )
        actual_growth = float(actual_by_month.loc[month]) / prior_actual - 1.0
        threshold = thresholds[month.month]
        rows.append({
            "month": month,
            "actual_revenue_usd": float(actual_by_month.loc[month]),
            "predicted_revenue_usd": float(prediction_by_month.loc[month]),
            "actual_yoy_growth_pct": actual_growth * 100,
            "train_only_monthly_cutoff_pct": threshold * 100,
            "anomaly_label": int(actual_growth < threshold),
            "predicted_yoy_growth_pct": prior_prediction[month] * 100,
            "downside_risk_score": -prior_prediction[month],
        })
    scored = pd.DataFrame(rows)
    positives = int(scored["anomaly_label"].sum())
    negatives = int(len(scored) - positives)
    result: dict[str, Any] = {
        "definition": (
            "Anomaly = actual same-calendar-month YoY growth below the calendar-month "
            f"{tail_quantile:.0%} quantile of training YoY growth (2017Ã¢â‚¬â€œ2023)."
        ),
        "threshold_source": "training actuals only; per-calendar-month quantile",
        "tail_quantile": tail_quantile,
        "positive_count": positives,
        "negative_count": negatives,
        "observation_count": int(len(scored)),
        "score_definition": "negative recursively predicted same-month YoY growth; higher means greater downside risk",
        "roc_auc": None,
        "gini": None,
        "status": "valid",
        "note": "AUC/Gini are undefined if either class is absent; no fallback or threshold tuning is applied.",
        "monthly_cutoffs_pct": {str(k): v * 100 for k, v in thresholds.items()},
        "rows": scored,
    }
    if positives == 0 or negatives == 0:
        result["status"] = "undefined_single_class"
    else:
        result["roc_auc"] = float(roc_auc_score(scored["anomaly_label"], scored["downside_risk_score"]))
        result["gini"] = 2 * result["roc_auc"] - 1
    return result


def evaluate_forecast(
    data_path: str | Path = DEFAULT_DATA_PATH,
    predictions_path: str | Path = PREDICTIONS_PATH,
) -> dict[str, Any]:
    """Evaluate existing frozen predictions; never fits/retrains the Phase 3 model."""
    data = load_sales_data(data_path)
    train, test = temporal_split(data)
    predictions = pd.read_csv(predictions_path, parse_dates=["month"])
    required = {"month", "predicted_revenue_usd"}
    if not required.issubset(predictions.columns):
        raise ValueError(f"Prediction artifact missing columns: {sorted(required - set(predictions.columns))}")
    predictions = predictions.loc[:, ["month", "predicted_revenue_usd"]].copy()
    predictions["month"] = pd.to_datetime(predictions["month"], errors="raise")
    predictions["predicted_revenue_usd"] = pd.to_numeric(predictions["predicted_revenue_usd"], errors="raise")
    actual_months = pd.DatetimeIndex(test["month"])
    predicted_months = pd.DatetimeIndex(predictions["month"])
    if len(predictions) != len(test) or not predicted_months.equals(actual_months):
        raise ValueError("Prediction dates must match all 24 test dates exactly and in order")
    if predictions["predicted_revenue_usd"].isna().any() or not np.isfinite(predictions["predicted_revenue_usd"]).all():
        raise ValueError("Prediction values must be finite and non-null")

    metrics = regression_metrics(test["revenue_usd"], predictions["predicted_revenue_usd"])
    k2 = calculate_k2_rmsse(train["revenue_usd"], test["revenue_usd"], predictions["predicted_revenue_usd"])
    train_features = build_features(train)
    # Recreate holdout feature history with recursive predictions only, never test actuals.
    from .sales_forecast import make_recursive_features
    recursive_history = train["revenue_usd"].astype(float).tolist()
    recursive_rows = []
    for row in predictions.itertuples(index=False):
        recursive_rows.append(make_recursive_features(row.month, recursive_history, len(recursive_history)))
        recursive_history.append(float(row.predicted_revenue_usd))
    test_features = pd.concat(recursive_rows, ignore_index=True)
    train_mask = train["month"].between(TRAIN_START, TRAIN_END)
    psi_rows = []
    for feature in FEATURE_COLUMNS:
        reference = train_features.loc[train_mask, feature]
        if feature in {"year", "trend"}:
            # Exclude monotonic time indexes: their shift is guaranteed by chronology.
            continue
        comparison = test_features[feature]
        calculated = calculate_psi(reference, comparison)
        psi_rows.append({"feature": feature, **calculated})
    psi = pd.DataFrame(psi_rows).sort_values("psi", ascending=False, ignore_index=True)

    # This label uses actuals only for evaluation. The score is computed exclusively
    # from frozen forecasts and information available at each forecast origin.
    gini_result = anomaly_gini(train, test, predictions)
    anomaly_rows: pd.DataFrame = gini_result.pop("rows")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "evaluation_period": {"start": str(TEST_START.date()), "end": str(TEST_END.date())},
        "observation_count": int(len(test)),
        "training_period": {"start": str(TRAIN_START.date()), "end": str(TRAIN_END.date())},
        "phase3_experiment_verified": {
            "algorithm": metadata.get("algorithm"),
            "random_state": metadata.get("random_state"),
            "training_target_rows": metadata.get("training_target_rows"),
            "prediction_count": metadata.get("recursive_prediction_count"),
            "prediction_path": str(Path(predictions_path)),
            "model_path": str(ARTIFACT_DIR / "sales_random_forest.joblib"),
            "no_retraining": True,
        },
        "regression_metrics": metrics,
        "psi": {
            "method": "10 train-quantile bins (unique quantile boundaries; infinite tails), epsilon floor 1e-6 then renormalize",
            "reference_period": "2016-01 to 2023-12",
            "comparison_period": "2024-01 to 2025-12",
            "variables": psi[["feature", "psi", "reference_non_null", "comparison_non_null"]].to_dict(orient="records"),
            "interpretation_guidance": "Common heuristic: <0.10 small, 0.10Ã¢â‚¬â€œ0.25 moderate, >=0.25 material; not universal thresholds.",
            "business_mix_note": "Consolidated-only data cannot measure outsourcing/headhunting/training mix stability.",
        },
        "anomaly_gini": {key: value for key, value in gini_result.items() if key != "monthly_cutoffs_pct"},
        "k2_score": {
            **k2,
            "name": "Nexova K2 Score (operationally defined as RMSSE)",
            "formula": "sqrt(test MSE / training seasonal-naive MSE at lag 12)",
            "training_period": "2016-01 to 2023-12",
            "evaluation_period": "2024-01 to 2025-12",
            "denominator_source": "training actual revenue only; 84 seasonal-naive differences",
            "interpretation": "<1: below seasonal-naive reference scale; =1: equal; >1: above reference scale.",
            "not_accuracy_percentage_or_probability": True,
        },        "limitations": [
            "Only 24 monthly holdout observations; PSI and ROC-AUC/Gini have substantial sampling uncertainty.",
            "The anomaly cutoff is a declared training-only seasonal lower-tail rule, not an externally validated business loss threshold.",
            "PSI describes observed consolidated-series feature distributions, not business-line mix stability.",
            "No confidence intervals or visualizations are produced in Phase 4.",
        ],
    }
    return {"report": report, "psi_detail": psi, "anomaly_detail": anomaly_rows}


def save_evaluation(result: dict[str, Any]) -> None:
    """Persist only new evaluation outputs; original training artifacts are read-only."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    result["psi_detail"].to_csv(PSI_PATH, index=False)
    result["anomaly_detail"].to_csv(ANOMALY_PATH, index=False, date_format="%Y-%m-%d")
    REPORT_JSON_PATH.write_text(json.dumps(result["report"], indent=2, allow_nan=False, ensure_ascii=True), encoding="utf-8")
    metrics = result["report"]["regression_metrics"]
    gini = result["report"]["anomaly_gini"]
    psi = result["report"]["psi"]["variables"]
    lines = [
        "# Nexova Sales Forecast Ã¢â‚¬â€ Phase 4 Evaluation", "",
        f"Evaluation: {result['report']['evaluation_period']['start']} to {result['report']['evaluation_period']['end']} ({result['report']['observation_count']} months).", "",
        "## Regression metrics", "",
        f"- MSE: {metrics['mse_usd_squared']:,.2f} USDÃ‚Â²",
        f"- RMSE: {metrics['rmse_usd']:,.2f} USD",
        f"- RMSE / mean actual revenue: {metrics['rmse_pct_of_mean_actual']:.2f}%", "",
        "MSE squares each residual and averages the squares, so its unit is USDÃ‚Â² and large misses receive extra weight. RMSE is the square root of MSE, returns to USD, and is easier to compare with monthly revenue amounts. The normalized RMSE divides it by mean actual test revenue.", "",
        "## PSI by variable", "", "| Feature | PSI | Guidance |", "|---|---:|---|",
    ]
    for row in psi:
        value = row["psi"]
        guidance = "small" if value < 0.10 else "moderate" if value < 0.25 else "material"
        lines.append(f"| {row['feature']} | {value:.4f} | {guidance} (heuristic) |")
    lines += ["", "PSI edges are train-only quantiles; duplicated quantile edges are collapsed. A small epsilon prevents zero-count/logarithm issues. Heuristic bands (<0.10, 0.10Ã¢â‚¬â€œ0.25, Ã¢â€°Â¥0.25) are not universal. This consolidated-only dataset does not support measuring outsourcing/headhunting/training mix stability.", "", "## Downside anomaly ranking", "", gini["definition"], gini["score_definition"], f"Labels: {gini['positive_count']} anomalous and {gini['negative_count']} normal months out of {gini['observation_count']}.", ""]
    if gini["roc_auc"] is None:
        lines.append(f"ROC-AUC/Gini not defined: {gini['status']}.")
    else:
        lines += [f"- ROC-AUC: {gini['roc_auc']:.4f}", f"- Gini = 2 Ãƒâ€” ROC-AUC Ã¢Ë†â€™ 1: {gini['gini']:.4f}"]
    k2 = result["report"]["k2_score"]
    lines += ["", "The cutoff is the 10th percentile of training same-calendar-month YoY growth, so August is compared with August history rather than treated as anomalous merely for its usual seasonal dip. The risk score is negative recursively predicted same-month YoY growth; high scores mean forecast downside risk. Actuals create labels only and prediction errors do not define anomalies.", "", "## K2 Score", "", f"Nexova K2 Score (operational definition: RMSSE): **{k2['value']:.6f}**.", "", f"Formula: sqrt(test MSE / training seasonal-naive MSE), lag {k2['seasonal_period_months']} months.", f"- Test MSE numerator (24 frozen predictions): {k2['numerator_test_mse']:.2f} USD^2", f"- Training-only denominator (84 seasonal differences, 2016-01–2023-12): {k2['denominator_training_seasonal_naive_mse']:.2f} USD^2", "- Interpretation: below 1 is below the seasonal-naïve reference scale; 1 is equal; above 1 exceeds it. Not an accuracy percentage or probability.", "- K2 is a Nexova project name for this RMSSE operationalization, not a universal metric name.", "", "## Limitations", "", *[f"- {item}" for item in result["report"]["limitations"]], "", "No Phase 5 visualization has been created."]
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    evaluated = evaluate_forecast()
    save_evaluation(evaluated)
    print(json.dumps(evaluated["report"], indent=2))
