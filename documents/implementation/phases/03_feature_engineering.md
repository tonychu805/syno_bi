# Feature Engineering Implementation Guide

## Objective
Transform preprocessed tables into model-ready datasets that capture quarterly patterns, seasonality, and external drivers required for next-quarter SVR-RM T1/T2/T3 forecasts (overall + top customers), regional volume/revenue forecasts, and SVR-DT-DS consumer trend insights with ≤2% forecast error.

## Responsibilities
- Design reproducible feature pipelines aligned with business hypotheses, assuming upstream preprocessing already applied the null-handling and enrichment rules defined in `documents/strategy/null_analysis.md`
- Maintain feature provenance via dbt model documentation and Python metadata manifests
- Store prepared features in `data/processed/features/` and Postgres feature marts for reuse
- Deliver SVR-RM forecasting feature marts (overall & customer-level), regional feature marts, consumer SVR-DT-DS trend views, and a general feature view that supports Metabase exploration

## Inputs & Outputs
- Inputs: Preprocessed Synology sale-out datasets aggregated to quarter with SVR-RM tags, customer revenue ranks, regional attributes, SVR-DT-DS consumer flags, and the completed null-handling from Phase 2 (currency fills, region lookups, bay enrichment); calendar/event tables; configuration for quarterly lags and aggregations
- Outputs: Training and scoring feature tables with documented schema, quarter-specific signals for quantity and revenue across product, customer, and regional dimensions, plus consumer trend features and feature importance notes

## Implementation Steps
1. Identify core feature sets (quarterly lags, rolling stats, categorical encodings, promotions) for SVR-RM overall demand, top-customer contributions, regional performance, and SVR-DT-DS consumer indicators; align them to dbt intermediate/mart models and explicitly reference which upstream-filled columns (e.g. `Region`, `exchange_rate_to_usd`, `total_bays`) are required
2. Produce companion “all-products” feature views so Metabase can remain fully interactive while the forecasting module consumes the SVR-RM and regional slices
3. Implement composable feature builders in `src/features/` with dependency injection for configs and Postgres read/write adapters that respect forecast cutoff dates, avoiding re-imputation that would duplicate Phase 2 logic
4. Implement feature store interface (parquet/pickle + Postgres tables) and metadata manifest (YAML or JSON)
5. Integrate feature quality checks (missingness, variance, leakage detection) before persisting—validate both global and filtered cohorts—and surface results through dbt docs or Airflow task logs; flag discrepancies against Phase 2 null expectations

## Testing & Validation
- Unit tests for each feature builder verifying mathematical correctness
- Integration tests ensuring entire feature pipeline produces expected shapes and keys
- Statistical validation comparing feature distributions across time windows

## Tooling & Dependencies
- pandas, numpy, scipy; optional featuretools or kats for time-series utilities
- dbt exposures for documenting feature marts; pytest, great_expectations or pandera for data quality assertions

## Risks & Mitigations
- Feature leakage: enforce cutoff dates and add automated guards in tests
- Feature bloat: track feature usage and prune low-impact columns periodically

## Deliverables & Checkpoints
- Feature module with manifest documenting each column’s definition and owner
- Reusable notebook demonstrating feature introspection with export plan
- CI job validating feature pipeline on sample data
