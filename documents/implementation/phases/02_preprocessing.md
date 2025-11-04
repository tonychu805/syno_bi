# Preprocessing Implementation Guide

## Objective
Standardize raw tabular exports into clean, typed, and join-ready tables that enable quarterly forecasts for SVR-RM T1/T2/T3 (overall and top customers), regional demand forecasts, and SVR-DT-DS consumer trend analysis with ≤2% error on forecasted metrics.

## Responsibilities
- Normalize column naming (snake_case), enforce dtype schema, and apply the null-handling rules codified in `documents/strategy/null_analysis.md` via `src/ingestion/sales_cleaning.py` so downstream quarterly aggregations for SVR-RM, regional, and SVR-DT-DS views stay deterministic
- Record transformation rules (column trimming, imputation, enrichment joins) in code, dbt YAML files, and documentation for auditability
- Preserve immutable raw snapshots by writing results to `data/processed/preprocessed/` and loading curated tables into the warehouse Postgres instance
- Maintain explicit filters/flags for SVR-RM T1/T2/T3 (forecast cohort), top-customer rankings, regional groupings, and SVR-DT-DS consumer segments while retaining the full product catalog for BI exploration

## Inputs & Outputs
- Inputs: Serialized Synology sale-out ingestion artifacts (pickle/CSV), schema definitions, cleaning config, and tagging rules for SVR-RM T1/T2/T3, regional dimensions, and SVR-DT-DS consumer segments
- Outputs: Curated tables materialized as dbt staging/intermediate models in Postgres containing quarterly-ready quantity and revenue fields (global + filtered), top-customer indicators, and consumer trend attributes alongside profiling reports

## Implementation Steps
1. Define canonical schema per dataset (dtypes, expected ranges, categorical mappings) in shared YAML configs and dbt `schema.yml` files, annotating expected null-handling behaviour from `null_analysis.md`
2. Implement and maintain the consolidated cleaning pipeline (`clean_sales` in the `syno_transform` DAG backed by `run_sales_cleaning_pipeline`) that executes the documented trimming, imputation, enrichment, and audit logging rules before writing the unified parquet to `data/processed`
3. Build dbt staging models that consume the cleaned seeds, retain the curated column set, and surface QA tests aligned with the null-handling policy
4. Tag SVR-RM T1/T2/T3, compute customer revenue ranks, and enrich with regional/consumer flags while preserving the full product set so both focused and global marts can be materialized downstream
5. Configure dbt sources, seeds, and exposures so downstream marts and forecasting features inherit consistent lineage for all three question areas
6. Capture profiling metrics (null ratios, duplicates) and store in dbt docs or operational logs, slicing by forecast cohort, region, and consumer segment; refresh the null analysis when drift is detected

### Null Handling Strategy
- Column-level rules for trimming, dropping rows, and imputations are governed by `documents/strategy/null_analysis.md`; update that playbook whenever workbook schema changes occur
- Apply column trims for excessive-null attributes such as `Comments`, `Unit`, and other non-essential fields (>90% missing)
- Retain but fill categorical dimensions (`Region`, `Country`, `Currency`) using lookup joins or mode-based defaults to preserve forecasting cohorts
- Recompute monetary metrics (`usd_adjusted_total`, `usd_adjusted_price`) instead of direct imputation, ensuring `exchange_rate_to_usd` gaps are filled from the FX mapping
- Drop rows that fail critical grain requirements (`Customer`, `Product`, `Total`) and audit counts in Airflow task logs for traceability
- Document every deviation from the null playbook in this phase guide and in the staging data dictionary

### Sales Seeds Column Retention Policy
- Stage only the attributes needed for forecasting, BI self-service, and quality gates; drop invoice-only identifiers during staging to prevent join clutter, following the null-handling decisions above.
- Column handling for Synology sales seeds:
  - **Trim**: `PI`, `InvDate`, `ShipDate`, `DeliveryFrom`, `ShipTo`, `Comments`, `Currency`, `Price`, `Total`, `T/T Discount`, `Discount`, `source_sheet` unless a downstream reconciliation requires them. These fields either duplicate derived metrics or contain sparse free text, and null prevalence rules in `null_analysis.md` mark them for removal.
  - **Keep & Fill**: Core commercial grain (`Customer`, `Product`, `ItemCode`, `Type`, `sub_cat`, `Country`, mapped region attributes), temporal features (derived `sale_date`, `sale_quarter`), commercial metrics (`Quantity`, `usd_adjusted_total`, `usd_adjusted_price`, `total_cap`), and QA/FX controls (`exchange_rate_to_usd`). Use the defined imputation logic (mode fills, lookup joins, FX defaults) when nulls appear.
- Document the retained vs. dropped fields in the preprocessing data dictionary (`documents/implementation/sales_staging_data_dictionary.md`) and refresh whenever new workbook tabs or columns appear, calling out null-treatment per column.

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
