"""Regional forecast DAG."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from dags.utils import (
    COHORT_REGION,
    TRANSFORM_DATASET,
    default_dag_args,
    run_baseline_forecast,
)


def _train_region(**_: dict) -> None:
    run_baseline_forecast(cohort=COHORT_REGION)


with DAG(
    dag_id="syno_forecast_region",
    description="Quarterly regional volume/revenue forecasts.",
    schedule=[TRANSFORM_DATASET],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "forecast"],
) as dag:
    train_forecast = PythonOperator(
        task_id="train_region_forecast",
        python_callable=_train_region,
    )

    trigger_activation = TriggerDagRunOperator(
        task_id="trigger_activation",
        trigger_dag_id="syno_activation",
        conf={"cohort": COHORT_REGION},
        reset_dag_run=True,
    )

    train_forecast >> trigger_activation
