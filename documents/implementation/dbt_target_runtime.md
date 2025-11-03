# DBT Seed Permission Hotfix (November 2025)

## Problem Statement
- Airflow’s `syno_transform` DAG failed at the `dbt_seed_ingestion` task.
- dbt attempted to write compiled artifacts to `/opt/airflow/dbt/target/run/...`, which sits on a read-only layer inside the container.
- Resulting exception: `[Errno 13] Permission denied` when materialising `2023.csv` and `2024.csv`.

## Root Cause
- Numeric seed tables (`2023`, `2024`) were renamed via aliases, but dbt still wrote its temp output to the default `target` directory under `/opt/airflow/dbt`.
- That directory is part of the container image and not backed by a writable volume, so any write operation from dbt fails.

## Remediation
1. Updated `dags/utils.py` helper so every dbt invocation points to a writable directory:
   - Honors `DBT_TARGET_PATH_OVERRIDE` if present.
   - Defaults to `<repo>/dbt/target_runtime` and ensures the directory exists before execution.
2. Added `target_runtime` to `clean-targets` in `dbt/dbt_project.yml` so `dbt clean` clears the new location safely.
3. Ignored the new directory in `.gitignore` to keep compiled artifacts out of version control.
4. Appended `DBT_TARGET_PATH_OVERRIDE=/opt/airflow/dbt/target_runtime` to `env/airflow.env` so Airflow workers inherit the writable path automatically.

## Follow-Up Actions
- Restart Airflow services (`docker compose restart airflow-scheduler airflow-worker`) so the new environment variable is loaded.
- Re-run the `syno_transform` DAG and confirm dbt seeds complete without permission errors.
- Inspect legacy paths (`/opt/airflow/dbt/target`) inside the container and clean up any orphaned files once convenient.
- Document this override in deployment playbooks (`documents/implementation/phases/05_pipelines.md`) during the next scheduled documentation sweep.
