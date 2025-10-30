# Preprocessing Implementation Guide

## Objective
Standardize raw tabular exports into clean, typed, and join-ready tables to feed feature generation and modeling pipelines.

## Responsibilities
- Normalize column naming (snake_case), enforce dtype schema, and handle nulls via dbt staging models and reusable pandas utilities
- Record transformation rules in code, dbt YAML files, and documentation for auditability
- Preserve immutable raw snapshots by writing results to `data/processed/preprocessed/` and loading curated tables into Supabase

## Inputs & Outputs
- Inputs: Serialized Synology sale-out ingestion artifacts (pickle/CSV), schema definitions, cleaning config
- Outputs: Curated tables materialized as dbt staging/intermediate models in Supabase, alongside local summary statistics and profiling reports

## Implementation Steps
1. Define canonical schema per dataset (dtypes, expected ranges, categorical mappings) in shared YAML configs and dbt `schema.yml` files
2. Build dbt staging models (and supporting `src/preprocessing/cleaning.py` helpers) that apply deterministic transforms before loading to Supabase
3. Configure dbt sources, seeds, and exposures so downstream marts and forecasting features inherit consistent lineage
4. Capture profiling metrics (null ratios, duplicates) and store in dbt docs or operational logs

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
