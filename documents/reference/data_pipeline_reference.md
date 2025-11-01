# Data Pipeline Reference

This document summarises the end-to-end workflow that powers the Synology BI platform, from raw data intake to dashboard delivery. Use it as a quick guide when operating or extending the stack.

## 1. Raw Data Intake

| Item | Details |
| --- | --- |
| Source | Synology sale-out Excel workbooks delivered as read-only snapshots. |
| Location | `raw/` (never modify files in-place). |
| Trigger | Manual drop or upstream file sync. |

### Operator Notes
- Keep filename/versioning intact for traceability.
- Store older snapshots for audit; the ingestion step is idempotent so re-processing is safe.

## 2. Ingestion Layer (Python)

| Item | Details |
| --- | --- |
| Entry point | `src/ingestion/excel_to_dataframes.py` |
| Runtime | Python 3.11 (pandas, openpyxl) |
| Output | One CSV or pickle per worksheet under `data/processed/ingestion/` |
| Airflow task | `ingest_excel` in `dags/synology_pipeline.py` |

### CLI Invocation
```bash
docker compose exec airflow-webserver \
  python /opt/airflow/src/ingestion/excel_to_dataframes.py \
  raw/synosales_2023.1-2024.12.xlsx \
  data/processed/ingestion \
  --format csv
```

### Responsibilities
- Sanitize worksheet names for filesystem safety.
- Preserve schema fidelity (no type coercion beyond pandas defaults).
- Avoid mutating source `raw/` files.

## 3. Staging Models (dbt)

| Item | Details |
| --- | --- |
| Tooling | dbt Core (SQL + YAML) running inside `dbt-runner` container |
| Warehouse | Postgres (`syno_bi` database, `analytics` schema) |
| Inputs | CSV outputs from ingestion (mounted or loaded via COPY) |
| Outputs | Cleaned staging tables with column typing, renamed headers, merged sheets |

### Standard Commands
```bash
docker compose exec dbt-runner bash
dbt deps
dbt run --select staging+
dbt test --select staging+
exit
```

### Documentation
- dbt docs served by the `dbt-docs` service at `http://<NAS-IP>:8081`.
- Update YAML files under `dbt/models/**/schema.yml` to describe columns, tests, and owners.

## 4. Marts & Business Logic

| Item | Details |
| --- | --- |
| Purpose | Produce fact/dimension tables aligned to KPIs (sales, channel performance, marketing metrics). |
| Recommended structure | `dbt/models/marts/` organised by domain (e.g., `sales`, `marketing`). |
| Validation | Add custom dbt tests (uniqueness, referential integrity) and maintain exposures/metrics metadata. |

### Best Practices
- Reference staging models (`ref('stg_synology_sales')`) rather than raw sources.
- Document owners and refresh cadence in YAML.
- For expensive models, consider incremental strategies (`materialized='incremental'`) once requirements stabilise.

## 5. Forecasting Layer (Python)

| Item | Details |
| --- | --- |
| Module | `src/forecasting/regression.py` |
| Task | `train_forecast` in Airflow DAG |
| Inputs | Aggregated sales history CSVs or dbt outputs |
| Outputs | Timestamped forecast CSVs + metadata JSON under `data/processed/forecasts/` |

### Execution
```bash
docker compose exec airflow-webserver \
  python -m src.forecasting.regression \
    --output-dir data/processed/forecasts
```

### Next Steps
- Expand feature set by querying dbt marts (e.g., promotions, inventory levels).
- Track accuracy metrics (MAPE, sMAPE) and store in metadata files.

## 6. Visualization & Activation

| Item | Details |
| --- | --- |
| Tool | Metabase (container `metabase`) |
| Warehouse connection | Host `postgres`, DB `syno_bi`, schema `analytics` |
| Refresh | Triggered via Airflow `refresh_metabase` task (optional webhook to n8n). |

### Deliverables
- Executive dashboards referencing dbt-derived tables and forecast outputs.
- Collections documenting data definitions and ownership.
- For ad-hoc queries, pgAdmin (connected to `postgres` service) provides schema and SQL access.

## 7. Orchestration (Airflow)

| DAG | `synology_pipeline.py` |
| --- | --- |
| Order | Ingestion → dbt run → dbt test → Forecast → Metabase refresh |
| Schedule | Configure via Airflow UI (`http://<NAS-IP>:8080`) |
| Alerts | Set `PIPELINE_ALERT_RECIPIENTS` in `env/airflow.env` for email notifications. |

### Operational Commands
- View logs: `docker compose logs --tail=50 airflow-webserver`
- Trigger run: Airflow UI → DAGs → `synology_bi_pipeline` → Trigger
- Pause/resume: Use Airflow UI or CLI (`airflow dags pause <dag_id>`).

## 8. Governance & Security

- **Postgres roles**: `airflow` (metadata), `analytics` (dbt), `metabase`, add more as needed. Manage via pgAdmin after attaching it to the `repo_default` network.
- **Secret storage**: Keep real credentials in `env/*.env` on NAS (not checked into Git). Rotate `AIRFLOW_DB_PASSWORD`, warehouse credentials, and Metabase tokens periodically.
- **Logging**: Airflow logs under `infra/airflow/logs`, Metabase data under `infra/metabase/data`.
- **Backups**: Snapshot `infra/postgres/data`, `infra/airflow/logs`, forecast artifacts, and `dbt/target` if required.

## 9. Developer Workflow Summary

1. **Update code/models** locally → push to GitHub.
2. **CI** runs lint/tests/dbt compile (`.github/workflows/ci.yml`).
3. **Deploy** via NAS (`git pull`, `docker compose up -d`).
4. **Run** Airflow DAG or manual CLI to refresh data.
5. **Verify** outputs in Metabase/pgAdmin/dbt docs.
6. **Document** changes in `documents/` and update runbooks/tests.

## 10. Quick Reference Commands

| Purpose | Command |
| --- | --- |
| Start full stack | `docker compose up -d` |
| Restart Airflow webserver | `docker compose up -d airflow-webserver` |
| Check container health | `docker compose ps` |
| Enter dbt shell | `docker compose exec dbt-runner bash` |
| Serve dbt docs | `docker compose up -d dbt-docs` (then browse `http://<NAS-IP>:8081`) |
| Run ingestion manually | `python src/ingestion/excel_to_dataframes.py ...` (within container) |
| Trigger DAG | Airflow UI or `airflow dags trigger synology_bi_pipeline` |

---

For deeper implementation details, see the individual guides in `documents/01_implementation_ingestion.md` through `documents/09_platform_environment.md`.
