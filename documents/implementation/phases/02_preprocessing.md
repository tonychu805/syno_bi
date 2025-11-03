# Preprocessing Implementation Guide

## Objective
Standardize raw tabular exports into clean, typed, and join-ready tables that enable quarterly forecasts for SVR-RM T1/T2/T3 (overall and top customers), regional demand forecasts, and SVR-DT-DS consumer trend analysis with ≤2% error on forecasted metrics.

## Responsibilities
- Normalize column naming (snake_case), enforce dtype schema, and handle nulls via dbt staging models and reusable pandas utilities so downstream quarterly aggregations for SVR-RM, regional, and SVR-DT-DS views stay deterministic
- Record transformation rules in code, dbt YAML files, and documentation for auditability
- Preserve immutable raw snapshots by writing results to `data/processed/preprocessed/` and loading curated tables into the warehouse Postgres instance
- Maintain explicit filters/flags for SVR-RM T1/T2/T3 (forecast cohort), top-customer rankings, regional groupings, and SVR-DT-DS consumer segments while retaining the full product catalog for BI exploration

## Inputs & Outputs
- Inputs: Serialized Synology sale-out ingestion artifacts (pickle/CSV), schema definitions, cleaning config, and tagging rules for SVR-RM T1/T2/T3, regional dimensions, and SVR-DT-DS consumer segments
- Outputs: Curated tables materialized as dbt staging/intermediate models in Postgres containing quarterly-ready quantity and revenue fields (global + filtered), top-customer indicators, and consumer trend attributes alongside profiling reports

## Implementation Steps
1. Define canonical schema per dataset (dtypes, expected ranges, categorical mappings) in shared YAML configs and dbt `schema.yml` files
2. Build dbt staging models (and supporting `src/preprocessing/cleaning.py` helpers) that apply deterministic transforms before loading to Postgres
3. Tag SVR-RM T1/T2/T3, compute customer revenue ranks, and enrich with regional/consumer flags while preserving the full product set so both focused and global marts can be materialized downstream
4. Configure dbt sources, seeds, and exposures so downstream marts and forecasting features inherit consistent lineage for all three question areas
5. Capture profiling metrics (null ratios, duplicates) and store in dbt docs or operational logs, slicing by forecast cohort, region, and consumer segment

## Testing & Validation
- Unit tests covering edge cases (unexpected categories, missing columns)
- Property-based checks for numerical ranges using hypothesis or custom assertions
- dbt tests (unique, not_null, accepted_values) and regression fixtures to ensure schema changes are intentional

## Tooling & Dependencies
- dbt (Postgres adapter) for transformation orchestration; pandas/numpy for supplemental preprocessing
- pytest, hypothesis, ruff, black for code quality; pandera or pydantic optional for additional schema validation

## Risks & Mitigations
- Schema drift: implement versioned schemas and automated alerts on mismatch
- Data quality degradation: schedule periodic profiling and track metrics over time

## Deliverables & Checkpoints
- Preprocessing module with documentation and ≥80% test coverage
- Data dictionary updated in `documents/data_prep.md`
- Automated report showing key quality metrics per release
