"""Synology C2 adoption scorecard DAG."""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from dags.utils import (
    COHORT_C2_ADOPTION,
    TRANSFORM_DATASET,
    build_c2_adoption_scorecard,
    default_dag_args,
    export_c2_scorecard,
)


with DAG(
    dag_id="syno_c2_adoption",
    description="Refresh Synology C2 adoption scorecard derived from sale-out data.",
    schedule=[TRANSFORM_DATASET],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_dag_args(),
    tags=["synology", "c2"],
) as dag:
    build_scorecard = PythonOperator(
        task_id="build_c2_adoption_scorecard",
        python_callable=build_c2_adoption_scorecard,
    )

    export_scorecard = PythonOperator(
        task_id="export_c2_scorecard",
        python_callable=export_c2_scorecard,
    )

    trigger_activation = TriggerDagRunOperator(
        task_id="trigger_activation",
        trigger_dag_id="syno_activation",
        conf={"cohort": COHORT_C2_ADOPTION},
        reset_dag_run=True,
    )

    build_scorecard >> export_scorecard >> trigger_activation
