# Pipeline & Automation Implementation Guide

## Objective
Orchestrate ingestion, preprocessing, feature engineering, and forecasting steps into a repeatable, observable workflow that teams can schedule and monitor.

## Responsibilities
- Package individual modules into orchestrated Airflow DAGs with clear boundaries and dependencies
- Provide CLI and programmatic entry points for full and incremental runs (Airflow CLI, dbt CLI)
- Instrument logging, error handling, and alerts for proactive operations
- Trigger Metabase dashboard refreshes or cache invalidations once new sale-out outputs land (via n8n or Airflow)

## Inputs & Outputs
- Inputs: Module-level configs, environment variables, orchestration metadata, dbt project files
- Outputs: Airflow run logs, Postgres table refresh status, Metabase dashboard refresh confirmations or cache clears, success/failure notifications

## Airflow DAG Topology

### 1. Raw Intake (`syno_ingestion`)
- `wait_for_workbook` (sensor) monitors `data/raw/` for new snapshots.
- `validate_snapshot` records checksum, size deltas, and schema sanity.
- `split_excel_tabs` invokes `python -m src.ingestion.excel_to_dataframes` to persist each worksheet.
- `publish_ingestion_manifest` writes run metadata (sheets, row counts, file hash) for downstream triggers.
- **Outputs**: per-sheet CSV/PKL in `data/processed/ingestion/`, manifest dataset for downstream DAGs.

### 2. Transform (`syno_transform`)
- Triggered via Airflow Dataset or `ExternalTaskSensor` once ingestion completes.
- `prep_reference_data` ensures mapping tables (region, device bays) are present and versioned.
- `clean_sales` runs `python -m src.ingestion.sales_cleaning` (sheet-filtered) to create consolidated parquet.
- `dbt_staging` kicks off `dbt run --select staging+`.
- `dbt_tests` executes `dbt test --select staging+`; failures halt downstream work.
- `dbt_marts` runs `dbt run --select marts+` to build KPI-aligned tables.
- `run_quality_gates` executes Great Expectations/SQL checks (row counts, null thresholds).
- `publish_lineage` updates metadata tables with run_id, row counts, data freshness.
- **Outputs**: cleaned parquet, staging/mart tables refreshed in warehouse, quality reports.

### 3. Forecast (`syno_forecast`)
- Scheduled daily/weekly or triggered off transform completion.
- `fetch_training_set` queries staging/marts, stores training snapshot.
- `train_forecast` calls `python -m src.forecasting.regression`.
- `evaluate_forecast` computes accuracy metrics (MAPE, sMAPE) and compares against thresholds.
- `store_model_artifacts` writes model, metrics, and provenance metadata to `data/processed/forecasts/`.
- `publish_forecast_outputs` loads forecast tables back to warehouse for BI consumption.
- `notify_forecast_status` alerts stakeholders if metrics trend down or new versions land.

### 4. Activation (`syno_activation`)
- `refresh_metabase` triggers Metabase API or n8n webhook to refresh dashboards.
- `send_summary_notifications` posts Slack/Teams summaries covering ingestion volume, dbt health, forecast metrics.
- `update_data_catalog` syncs exposures/lineage back to catalog tooling (optional).

## Implementation Steps
1. Provision Airflow on the Synology NAS (Docker Compose or Kubernetes) with connections for Postgres, Metabase, dbt.
2. Split orchestration into the four DAGs above; wire them with Airflow Datasets/`ExternalTaskSensor` to enforce order and allow independent reruns.
3. Centralize configuration (YAML + env overrides) and secrets via Airflow Variables/Connections or Vault.
4. Build TaskGroups within each DAG (e.g., validation, dbt, quality) for readability; log row counts and durations.
5. Integrate dbt run/test, forecasting scripts, and Metabase refresh calls; surface all CLI equivalents in docs.
6. Implement observability: structured logs, audit tables capturing run metadata, alerting routes (email/Slack).

## Testing & Validation
- Unit tests for each task wrapper and error-handling branch.
- Integration tests that execute the transform DAG against fixture workbooks.
- Dry-run mode verifying DAG dependency resolution without writing outputs.
- Post-deployment smoke test triggered from Airflow after major changes.

## Tooling & Dependencies
- Apache Airflow, dbt Core, pandas, PyArrow.
- n8n or custom webhooks for dashboard activation.
- Logging/metrics stack (e.g., structlog, Airflow task metrics, DataDog/Grafana).

## Risks & Mitigations
- **Orchestrator complexity**: start with the Transform DAG, add others incrementally.
- **Configuration drift**: enforce schema validation for env vars and reference tables.
- **Data freshness gaps**: add ingestion sensors and SLA alerts to detect late/missing snapshots.

## Deliverables & Checkpoints
- DAG definitions for ingestion, transform, forecast, activation committed under `dags/`.
- Runbook detailing restart procedures, alert routing, and on-call contact.
- CI pipeline executing linting, tests, and optional Dockerized pipeline smoke run.
- Data lineage/metadata tables populated after each transform run.
