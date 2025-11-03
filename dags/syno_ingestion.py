"""Ingestion DAG: load Synology workbooks and emit processed sheets."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from dags.utils import INGESTION_DATASET, default_dag_args, run_ingestion


with DAG(
    dag_id="syno_ingestion",
    description="Extract Synology Excel snapshots into processed tabular assets.",
    schedule_interval="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "ingestion"],
) as dag:
    ingest_excel = PythonOperator(
        task_id="ingest_excel",
        python_callable=run_ingestion,
        outlets=[INGESTION_DATASET],
    )
