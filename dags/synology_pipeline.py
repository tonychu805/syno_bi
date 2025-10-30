"""Airflow DAG orchestrating ingestion, dbt transforms, forecasting, and Tableau refresh."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.forecasting.regression import train_regression_forecast
from src.ingestion import excel_to_dataframes


def _repo_root() -> Path:
    """Infer the project root from the DAG location or env override."""
    override = os.environ.get("SYNOBI_REPO_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


def _run_ingestion(**_: Dict[str, Any]) -> None:
    """Invoke the ingestion pipeline against the configured workbook."""
    repo = _repo_root()
    default_source = repo / "raw" / "synosales_2023.1-2024.12.xlsx"
    excel_path = Path(os.environ.get("SYNOSALES_WORKBOOK", default_source))
    output_dir = Path(os.environ.get("INGESTION_OUTPUT_DIR", repo / "data" / "processed"))
    excel_to_dataframes.load_and_save_excel_tabs(
        excel_path=excel_path,
        output_dir=output_dir,
        fmt=os.environ.get("INGESTION_FORMAT", "csv"),
        include_index=False,
    )


def _run_dbt(command: str) -> None:
    """Run a dbt CLI command inside the project directory."""
    repo = _repo_root()
    dbt_dir = repo / "dbt"
    env = os.environ.copy()
    env.setdefault("DBT_PROFILES_DIR", str(dbt_dir))
    subprocess.run(
        command,
        cwd=dbt_dir,
        shell=True,
        env=env,
        check=True,
    )


def _dbt_run(**_: Dict[str, Any]) -> None:
    _run_dbt("dbt run --select staging+")


def _dbt_test(**_: Dict[str, Any]) -> None:
    _run_dbt("dbt test --select staging+")


def _run_forecast(**_: Dict[str, Any]) -> None:
    repo = _repo_root()
    artifacts_dir = Path(os.environ.get("FORECAST_ARTIFACTS_DIR", repo / "data" / "processed" / "forecasts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    train_regression_forecast(output_dir=artifacts_dir)


def _trigger_tableau_refresh(**_: Dict[str, Any]) -> None:
    """Trigger Tableau refresh via n8n webhook if configured."""
    webhook = os.environ.get("N8N_TABLEAU_WEBHOOK")
    if not webhook:
        return

    env = os.environ.copy()
    subprocess.run(
        ["curl", "-sf", "-X", "POST", webhook],
        env=env,
        check=True,
    )


default_args = {
    "owner": "bi_platform",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": os.environ.get("PIPELINE_ALERT_RECIPIENTS", "").split(","),
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

with DAG(
    dag_id="synology_bi_pipeline",
    default_args=default_args,
    description="Synology BI end-to-end pipeline",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["synology", "bi"],
) as dag:
    ingestion = PythonOperator(task_id="ingest_excel", python_callable=_run_ingestion)
    dbt_run = PythonOperator(task_id="dbt_run", python_callable=_dbt_run)
    dbt_test = PythonOperator(task_id="dbt_test", python_callable=_dbt_test)
    forecast = PythonOperator(task_id="train_forecast", python_callable=_run_forecast)
    tableau_refresh = PythonOperator(task_id="refresh_tableau", python_callable=_trigger_tableau_refresh)

    ingestion >> dbt_run >> dbt_test >> forecast >> tableau_refresh
