# Nexova forecast — Phase 3: Random Forest

## Scope and method

Phase 3 fits a `sklearn.ensemble.RandomForestRegressor` with `random_state=42` to the consolidated monthly revenue series. The 2016–2023 chronological training period contains 96 months; causal lag and rolling features require a 12-month warm-up, so 84 target rows (January 2017–December 2023) are used to fit the model. No target row from 2024–2025 is used for fitting, model selection, or recursive feature construction.

The fixed, conservative forest configuration is `n_estimators=300`, `max_depth=5`, `min_samples_split=4`, `min_samples_leaf=2`, `max_features=0.8`, and `n_jobs=-1`, with the required seed. This bounded model is chosen to limit complexity on the small monthly sample; no holdout-guided tuning is performed.

Forecasting proceeds one month at a time from January 2024 through December 2025. Each prediction's lag/rolling features use only the 2016–2023 actual history and predictions generated earlier in the same rollout. The 2024–2025 actual revenue values are not appended to forecast history. Actuals may be joined to predictions later for the separately authorized evaluation phase, but that join is deliberately not part of this phase.

## Reproduction

From the repository root, install the local requirements and run:

```powershell
pip install -r data/process/requirements.txt
python -m data.process.train_sales_forecast
```

The script uses `data/raw/nexova_sales.csv`, validates the existing 120-month consolidated series, and writes artifacts to `data/process/artifacts/`.

## Phase 3 outputs

- `sales_random_forest.joblib`: fitted estimator.
- `sales_forecast_predictions.csv`: 24 ordered months and `predicted_revenue_usd`; no test actuals or evaluation metrics.
- `feature_importance.csv`: descending impurity-based feature importance.
- `training_metadata.json`: date boundaries, feature names, row counts, seed, hyperparameters, and leakage-control note.

The run used 84 training targets and produced all 24 predictions. The leading feature was `revenue_lag_12` (importance approximately 0.753), followed by `month` (approximately 0.063) and `revenue_roll_mean_12` (approximately 0.045). These are model-internal impurity-based importances, not causal effects; correlated lag and rolling variables can divide or distort importance. They should be interpreted as descriptive diagnostics only.

## Validation and boundary

Phase 3 tests verify training target indices are limited to 2016–2023, all 24 recursive predictions/artifacts are produced, the seed and importances are recorded, and changing test actual revenues does not change forecasts. Phase 2 tests remain separate and are also run before handoff. The four planned evaluation metrics are intentionally not computed here. Stop after this phase pending explicit authorization for Phase 4.