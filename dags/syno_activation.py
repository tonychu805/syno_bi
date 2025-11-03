"""Activation DAG: refresh Metabase, send notifications, log summaries."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from dags.utils import (
    default_dag_args,
    log_activation_summary,
    trigger_metabase_refresh,
)


with DAG(
    dag_id="syno_activation",
    description="Post-forecast activation (dashboards, notifications).",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=3,
    default_args=default_dag_args(),
    tags=["synology", "activation"],
) as dag:
    refresh_metabase = PythonOperator(
        task_id="refresh_metabase",
        python_callable=trigger_metabase_refresh,
    )

    summarize = PythonOperator(
        task_id="log_activation_summary",
        python_callable=log_activation_summary,
    )

    refresh_metabase >> summarize
