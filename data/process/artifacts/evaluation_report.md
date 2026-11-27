# Nexova Sales Forecast Ã¢â‚¬â€ Phase 4 Evaluation

Evaluation: 2024-01-01 to 2025-12-01 (24 months).

## Regression metrics

- MSE: 3,812,985,067.19 USDÃ‚Â²
- RMSE: 61,749.37 USD
- RMSE / mean actual revenue: 6.44%

MSE squares each residual and averages the squares, so its unit is USDÃ‚Â² and large misses receive extra weight. RMSE is the square root of MSE, returns to USD, and is easier to compare with monthly revenue amounts. The normalized RMSE divides it by mean actual test revenue.

## PSI by variable

| Feature | PSI | Guidance |
|---|---:|---|
| revenue_roll_mean_12 | 12.2678 | material (heuristic) |
| revenue_roll_mean_6 | 10.8968 | material (heuristic) |
| revenue_roll_mean_3 | 9.4262 | material (heuristic) |
| revenue_lag_12 | 8.3323 | material (heuristic) |
| revenue_lag_2 | 8.1681 | material (heuristic) |
| revenue_lag_3 | 8.1071 | material (heuristic) |
| revenue_lag_6 | 8.1055 | material (heuristic) |
| revenue_lag_1 | 6.8678 | material (heuristic) |
| revenue_roll_std_12 | 4.1520 | material (heuristic) |
| month_cos | 0.0000 | small (heuristic) |
| month_sin | 0.0000 | small (heuristic) |
| quarter | 0.0000 | small (heuristic) |
| month | 0.0000 | small (heuristic) |

PSI edges are train-only quantiles; duplicated quantile edges are collapsed. A small epsilon prevents zero-count/logarithm issues. Heuristic bands (<0.10, 0.10Ã¢â‚¬â€œ0.25, Ã¢â€°Â¥0.25) are not universal. This consolidated-only dataset does not support measuring outsourcing/headhunting/training mix stability.

## Downside anomaly ranking

Anomaly = actual same-calendar-month YoY growth below the calendar-month 10% quantile of training YoY growth (2017Ã¢â‚¬â€œ2023).
negative recursively predicted same-month YoY growth; higher means greater downside risk
Labels: 3 anomalous and 21 normal months out of 24.

- ROC-AUC: 0.5714
- Gini = 2 Ãƒâ€” ROC-AUC Ã¢Ë†â€™ 1: 0.1429

The cutoff is the 10th percentile of training same-calendar-month YoY growth, so August is compared with August history rather than treated as anomalous merely for its usual seasonal dip. The risk score is negative recursively predicted same-month YoY growth; high scores mean forecast downside risk. Actuals create labels only and prediction errors do not define anomalies.

## K2 Score

Nexova K2 Score (operational definition: RMSSE): **1.181745**.

Formula: sqrt(test MSE / training seasonal-naive MSE), lag 12 months.
- Test MSE numerator (24 frozen predictions): 3812985067.19 USD²
- Training-only denominator (84 seasonal differences, 2016-01–2023-12): 2730346258.47 USD²
- Interpretation: below 1 is below the seasonal-naïve reference scale; 1 is equal; above 1 exceeds it. Not an accuracy percentage or probability.
- K2 is a Nexova project name for this RMSSE operationalization, not a universal metric name.

## Limitations

- Only 24 monthly holdout observations; PSI and ROC-AUC/Gini have substantial sampling uncertainty.
- The anomaly cutoff is a declared training-only seasonal lower-tail rule, not an externally validated business loss threshold.
- PSI describes observed consolidated-series feature distributions, not business-line mix stability.
- No confidence intervals or visualizations are produced in Phase 4.

No Phase 5 visualization has been created.
