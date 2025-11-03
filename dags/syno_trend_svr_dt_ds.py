"""SVR-DT-DS consumer trend refresh DAG."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from dags.utils import (
    COHORT_SVR_DT_DS_TREND,
    TRANSFORM_DATASET,
    default_dag_args,
    run_baseline_forecast,
)


def _refresh_trend(**_: dict) -> None:
    # Placeholder: reuse baseline forecast utility until dedicated trend job is implemented.
    run_baseline_forecast(cohort=COHORT_SVR_DT_DS_TREND)


with DAG(
    dag_id="syno_trend_svr_dt_ds",
    description="Refresh SVR-DT-DS consumer market trend metrics.",
    schedule=[TRANSFORM_DATASET],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "trend"],
) as dag:
    refresh_trend = PythonOperator(
        task_id="refresh_consumer_trend",
        python_callable=_refresh_trend,
    )

    trigger_activation = TriggerDagRunOperator(
        task_id="trigger_activation",
        trigger_dag_id="syno_activation",
        conf={"cohort": COHORT_SVR_DT_DS_TREND},
        reset_dag_run=True,
    )

    refresh_trend >> trigger_activation
