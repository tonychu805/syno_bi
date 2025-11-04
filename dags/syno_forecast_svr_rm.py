"""SVR-RM forecast DAG (overall + top customers)."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from dags.utils import (
    COHORT_SVR_RM,
    TRANSFORM_DATASET,
    default_dag_args,
    load_forecast_to_postgres,
    run_baseline_forecast,
)


def _train_svr_rm(**_: dict) -> None:
    run_baseline_forecast(cohort=COHORT_SVR_RM)


with DAG(
    dag_id="syno_forecast_svr_rm",
    description="Quarterly SVR-RM forecasts (overall and top customers).",
    schedule=[TRANSFORM_DATASET],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "forecast"],
) as dag:
    train_forecast = PythonOperator(
        task_id="train_svr_rm_forecast",
        python_callable=_train_svr_rm,
    )

    load_forecast = PythonOperator(
        task_id="load_forecast_to_postgres",
        python_callable=load_forecast_to_postgres,
        op_kwargs={
            "cohort": COHORT_SVR_RM,
            "table": "forecast_overall",
            "model_name": "baseline",
            "model_version": "rolling_mean_v1",
        },
    )

    trigger_activation = TriggerDagRunOperator(
        task_id="trigger_activation",
        trigger_dag_id="syno_activation",
        conf={"cohort": COHORT_SVR_RM},
        reset_dag_run=True,
    )

    train_forecast >> load_forecast >> trigger_activation
