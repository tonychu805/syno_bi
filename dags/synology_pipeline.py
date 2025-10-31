"""Airflow DAG orchestrating ingestion, dbt transforms, forecasting, and Metabase refresh."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.forecasting.regression import train_regression_forecast
from src.ingestion import (
    SalesCleaningConfig,
    excel_to_dataframes,
    run_sales_cleaning_pipeline,
)


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


def _run_sales_cleaning(**_: Dict[str, Any]) -> None:
    """Run the consolidated sales cleaning pipeline for selected sheets."""

    repo = _repo_root()
    default_workbook = repo / "data" / "raw" / "synosales_2023.1-2024.12.xlsx"
    workbook = Path(os.environ.get("SYNOSALES_WORKBOOK", default_workbook))

    sheet_list = os.environ.get("SALES_CLEAN_SHEETS", "2023-C2,2024-C2,2023,2024")
    include_sheets = [sheet.strip() for sheet in sheet_list.split(",") if sheet.strip()]

    config = SalesCleaningConfig(
        workbook_path=workbook,
        include_sheets=include_sheets,
    )

    cleaned = run_sales_cleaning_pipeline(config)

    output_path = Path(
        os.environ.get(
            "SALES_CLEAN_OUTPUT",
            repo / "data" / "processed" / "synosales_cleaned.parquet",
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(output_path, index=False)


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


def _trigger_metabase_refresh(**_: Dict[str, Any]) -> None:
    """Trigger Metabase dashboard refresh via n8n webhook if configured."""
    webhook = os.environ.get("N8N_METABASE_WEBHOOK")
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
    clean_sales = PythonOperator(task_id="clean_sales", python_callable=_run_sales_cleaning)
    dbt_run = PythonOperator(task_id="dbt_run", python_callable=_dbt_run)
    dbt_test = PythonOperator(task_id="dbt_test", python_callable=_dbt_test)
    forecast = PythonOperator(task_id="train_forecast", python_callable=_run_forecast)
    metabase_refresh = PythonOperator(task_id="refresh_metabase", python_callable=_trigger_metabase_refresh)

    ingestion >> clean_sales >> dbt_run >> dbt_test >> forecast >> metabase_refresh
