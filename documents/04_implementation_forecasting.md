# Forecasting Implementation Guide

## Objective
Build, evaluate, and operationalize forecasting models that generate reliable predictions and reproducible evaluation metrics.

## Responsibilities
- Select baseline and advanced models aligned with data cadence and business KPIs
- Maintain training, validation, and backtesting routines with clear version control
- Surface model metrics, artifacts, and interpretability outputs for stakeholders

## Inputs & Outputs
- Inputs: Feature datasets derived from Synology sale-out data, model hyperparameter configs, calendar splits, evaluation criteria
- Outputs: Forecasts stored in `data/processed/forecasts/`, metrics dashboards, and model registry entries

## Implementation Steps
1. Establish baseline forecasts (naïve, moving average) for comparison with dbt-exposed feature marts
2. Implement multiple linear regression training pipeline in `src/forecasting/`, sourcing features from Supabase/dbt models, and include feature scaling plus cross-validation tuned to ≤2% MAPE
3. Add evaluation module capturing MAPE, sMAPE, WAPE, coverage intervals, and stability metrics
4. Register artifacts (model params, coefficient snapshots, plots) back into Supabase or object storage and track in documents/model_eval.md for Metabase consumption

## Testing & Validation
- Unit tests for metric calculations and data split utilities
- Backtesting harness verifying incremental performance across time windows
- Performance regression tests to guard against deteriorating accuracy

## Tooling & Dependencies
- scikit-learn or statsmodels for linear regression; numpy/pandas baseline
- Supabase Python client for feature retrieval plus Airflow operators for scheduled retraining
- Optional experiment tracking (e.g., mlflow) if model lineage is required

## Risks & Mitigations
- Overfitting due to limited history: enforce temporal validation and regularization
- Concept drift: schedule retraining cadence with monitoring dashboards

## Deliverables & Checkpoints
- Forecasting module with documented pipelines and reproducible notebooks
- Automated evaluation report attached to releases
- Deployment-ready model artifacts with ownership and refresh cadence
