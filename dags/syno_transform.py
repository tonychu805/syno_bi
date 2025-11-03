"""Transform DAG: clean sales, run dbt, emit curated marts."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from dags.utils import (
    INGESTION_DATASET,
    TRANSFORM_DATASET,
    dbt_run_select,
    dbt_seed,
    dbt_test_select,
    default_dag_args,
    run_sales_cleaning,
)


def _run_dbt_staging(**_: dict) -> None:
    dbt_run_select("staging+")


def _test_dbt_staging(**_: dict) -> None:
    dbt_test_select("staging+")


with DAG(
    dag_id="syno_transform",
    description="Clean sales data and build dbt staging/marts.",
    schedule=[INGESTION_DATASET],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "transform"],
) as dag:
    clean_sales = PythonOperator(
        task_id="clean_sales",
        python_callable=run_sales_cleaning,
    )

    dbt_seed_ingestion = PythonOperator(
        task_id="dbt_seed_ingestion",
        python_callable=lambda **_: dbt_seed("synology_ingestion.*"),
    )

    dbt_run_staging = PythonOperator(
        task_id="dbt_run_staging",
        python_callable=_run_dbt_staging,
    )

    dbt_test_staging = PythonOperator(
        task_id="dbt_test_staging",
        python_callable=_test_dbt_staging,
        outlets=[TRANSFORM_DATASET],
    )

    clean_sales >> dbt_seed_ingestion >> dbt_run_staging >> dbt_test_staging
