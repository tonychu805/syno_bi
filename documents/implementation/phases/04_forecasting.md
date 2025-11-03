# Forecasting Implementation Guide

## Objective
Build, evaluate, and operationalize forecasting models that deliver next-quarter volume and revenue predictions for SVR-RM T1/T2/T3 (overall and top 5 customers) and regional demand, while providing consumer SVR-DT-DS trend outputs with reproducible metrics and ≤2% forecast error.

## Responsibilities
- Select baseline and advanced models aligned with quarterly cadence and business KPIs for SVR-RM cohorts and regional views
- Maintain training, validation, and backtesting routines with clear version control
- Surface model metrics, artifacts, and interpretability outputs for stakeholders

## Inputs & Outputs
- Inputs: Quarter-aggregated feature datasets derived from Synology sale-out data for SVR-RM T1/T2/T3 (overall + customer-level), regional slices, and consumer SVR-DT-DS trends; model hyperparameter configs, calendar splits, evaluation criteria; plus reference joins back to the all-product mart for dashboard enrichment
- Outputs: Next-quarter SVR-RM and regional forecast tables stored in `data/processed/forecasts/`, top-customer forecast breakouts, consumer trend summaries, metrics dashboards, and model registry entries that retain product/customer/region metadata for downstream Metabase analysis

## Implementation Steps
1. Establish baseline forecasts (naïve, rolling quarter averages) for SVR-RM overall, SVR-RM top customers, and regional cohorts; confirm coverage of quantity and revenue metrics
2. Implement regression/forecast pipelines in `src/forecasting/`, sourcing quarterly features from Postgres/dbt models, and include feature scaling plus cross-validation tuned to ≤2% MAPE on next-quarter holdouts for each cohort
3. Generate consumer SVR-DT-DS trend outputs (growth rates, share metrics) alongside the forecasts to support narrative analysis
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
