# Forecasting Implementation Guide

## Objective
Build, evaluate, and operationalize forecasting models that deliver next-quarter volume and revenue predictions for SVR-RM T1/T2/T3 (overall and top 5 customers), generate Synology C2 exploratory projections, and provide commercial activation insights with reproducible metrics and accuracy that meets business expectations.

## Responsibilities
- Select baseline and advanced models aligned with quarterly cadence and business KPIs for SVR-RM cohorts and Synology C2 exploratory views
- Maintain training, validation, and backtesting routines with clear version control
- Surface model metrics, artifacts, and interpretability outputs for stakeholders

## Inputs & Outputs
- Inputs: Quarter-aggregated feature datasets derived from Synology sale-out data for SVR-RM T1/T2/T3 (overall + customer-level), Synology C2 adoption cohorts, and commercial activation checkpoints; model hyperparameter configs, calendar splits, evaluation criteria; plus reference joins back to the all-product mart for dashboard enrichment
- Outputs: Next-quarter SVR-RM forecasts, Synology C2 exploratory scorecards stored in `data/processed/forecasts/`, top-customer forecast breakouts, activation summaries, metrics dashboards, and model registry entries that retain product/customer/C2 metadata for downstream Metabase analysis

### Key Artifacts
- `analytics.forecast_overall` (Objective 1): `forecast_run_id`, `cohort`, `model_name`, `model_version`, `sku`, `channel`, `sale_month`, `forecast_date`, `forecast_quantity`, `forecast_revenue`, `forecast_revenue_lower`, `forecast_revenue_upper`, `actual_quantity`, `actual_revenue`, `product_name`, `product_type`, `product_subcategory`, `created_at`.
- `analytics.c2_adoption_scorecard` (Objective 2): `snapshot_month`, `service_family`, `plan_variant`, `region`, `customer_tier`, `sku`, `active_subscriptions`, `new_subscriptions`, `mrr_usd`, `total_quantity`, `avg_seats`.
- `analytics.activation_storylines` (Objective 3): `snapshot_month`, `region`, `segment`, `actual_revenue`, `forecast_revenue`, `variance_pct`, `inventory_weeks_cover`, `market_index_score`, `activation_score`, `recommended_action`, `confidence_note`.

## Implementation Steps
1. Establish baseline forecasts (naïve, rolling quarter averages) for SVR-RM overall, SVR-RM top customers, and Synology C2 cohorts; confirm coverage of quantity and revenue metrics
2. Implement regression/forecast pipelines in `src/forecasting/`, sourcing quarterly features from Postgres/dbt models, and include feature scaling plus cross-validation tuned to achieve the agreed MAPE benchmarks on next-quarter holdouts for each cohort
3. Generate Synology C2 exploratory outputs (growth rates, retention signals, upsell opportunities) alongside the forecasts to support narrative analysis
4. Add evaluation modules capturing MAPE, sMAPE, WAPE, coverage intervals, and stability metrics per cohort; register artifacts (model params, coefficient snapshots, plots) back into Postgres or object storage and track in documents/model_eval.md for Metabase consumption

## Testing & Validation
- Unit tests for metric calculations and data split utilities
- Backtesting harness verifying incremental performance across time windows
- Performance regression tests to guard against deteriorating accuracy

## Tooling & Dependencies
- scikit-learn or statsmodels for linear regression; numpy/pandas baseline
- Postgres Python client (psycopg) for feature retrieval plus Airflow operators for scheduled retraining
- Optional experiment tracking (e.g., mlflow) if model lineage is required

## Risks & Mitigations
- Overfitting due to limited history: enforce temporal validation and regularization
- Concept drift: schedule retraining cadence with monitoring dashboards

## Deliverables & Checkpoints
- Forecasting module with documented pipelines and reproducible notebooks
- Automated evaluation report attached to releases
- Deployment-ready model artifacts with ownership and refresh cadence
