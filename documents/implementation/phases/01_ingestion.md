# Ingestion Implementation Guide

## Objective
Capture every worksheet in the Synology sale-out Excel snapshots and expose them as reusable data artifacts without mutating the source snapshots.

## Responsibilities
- Build and maintain `src/ingestion/excel_to_dataframes.py` CLI utility
- Ensure worksheet naming collisions are handled and outputs stored deterministically
- Keep ingestion logic idempotent so reruns yield identical artifacts
- Preserve product, customer, regional, and consumer-segment attributes required for SVR-RM, regional, and SVR-DT-DS analyses

## Inputs & Outputs
- Inputs: Excel workbooks under `raw/`, config for output directory, serialization format
- Outputs: Serialized DataFrames under `data/processed/ingestion/` (pickle by default, CSV optional) suitable for dbt seeds or Postgres staging loads, plus CLI logs summarizing saved sheets

## Implementation Steps
1. Finalize CLI options (engine override, format toggle, index persistence)
2. Add configurable destination path via config module to prevent hard-coded directories
3. Integrate ingestion step into the Airflow ingestion DAG so downstream dbt models and next-quarter forecasting jobs trigger reliably, with n8n handling any API notifications
4. Add logging and basic runtime metrics (duration, row counts)
5. Surface canonical SKU identifiers, customer IDs, regional codes, and consumer-segment markers so SVR-RM, top-customer, regional, and SVR-DT-DS cohorts can be filtered consistently in later phases

## Testing & Validation
- Unit tests in `tests/ingestion/test_excel_to_dataframes.py` using small fixture workbook
- CLI smoke test in CI to ensure argument parsing and serialization succeed
- Data validation: confirm row counts and column names match the source sheets

## Tooling & Dependencies
- pandas for Excel parsing, openpyxl for .xlsx engine
- Airflow task wrapper for scheduled execution and dbt seed refresh
- pytest + coverage for unit tests, ruff for linting

## Risks & Mitigations
- Engine compatibility: fall back to auto-detection and document overrides
- Large files causing memory strain: support optional sheet name filters in future iteration

## Deliverables & Checkpoints
- Code merged with tests ≥80% coverage
- README snippet or doc entry describing ingestion usage
- Pipeline task registered and observable in orchestration layer
