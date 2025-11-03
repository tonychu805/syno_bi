"""Shared helpers for Synology BI Airflow DAGs."""

from __future__ import annotations

import os
import subprocess
from datetime import timedelta
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, Optional

from airflow.datasets import Dataset
from airflow.utils.log.logging_mixin import LoggingMixin

from src.forecasting.regression import train_regression_forecast
from src.ingestion import (
    SalesCleaningConfig,
    excel_to_dataframes,
    run_sales_cleaning_pipeline,
)

LOG = LoggingMixin().log

# Dataset definitions to coordinate DAG dependencies.
INGESTION_DATASET = Dataset("synology://datasets/ingestion_complete")
TRANSFORM_DATASET = Dataset("synology://datasets/transform_complete")

# Optional cohort identifiers used when triggering activation DAGs.
COHORT_SVR_RM = "svr_rm"
COHORT_REGION = "region"
COHORT_SVR_DT_DS_TREND = "svr_dt_ds_trend"


def repo_root() -> Path:
    """Infer the repository root from the DAG location or env override."""
    override = os.environ.get("SYNOBI_REPO_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Ingestion / cleaning helpers
# ---------------------------------------------------------------------------


def run_ingestion(**_: Dict[str, Any]) -> None:
    """Invoke the ingestion pipeline against the configured workbook."""
    repo = repo_root()
    default_source = repo / "raw" / "synosales_2023.1-2024.12.xlsx"
    excel_path = Path(os.environ.get("SYNOSALES_WORKBOOK", default_source))
    default_output = repo / "dbt" / "seeds" / "synology_ingestion"
    output_dir = Path(os.environ.get("INGESTION_OUTPUT_DIR", default_output))
    fmt = os.environ.get("INGESTION_FORMAT", "csv")
    include_index = os.environ.get("INGESTION_INCLUDE_INDEX", "false").lower() == "true"
    mapping_src = repo / "data" / "mapping_table"
    mapping_dest = repo / "dbt" / "seeds" / "mapping_table"

    LOG.info("Starting ingestion for %s -> %s (%s)", excel_path, output_dir, fmt)
    output_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        for existing in output_dir.glob("*.csv"):
            existing.unlink(missing_ok=True)
    excel_to_dataframes.load_and_save_excel_tabs(
        excel_path=excel_path,
        output_dir=output_dir,
        fmt=fmt,
        include_index=include_index,
    )

    if mapping_src.exists():
        mapping_dest.mkdir(parents=True, exist_ok=True)
        for existing in mapping_dest.glob("*.csv"):
            existing.unlink(missing_ok=True)
        for csv_path in mapping_src.glob("*.csv"):
            shutil.copy(csv_path, mapping_dest / csv_path.name)


def run_sales_cleaning(**_: Dict[str, Any]) -> None:
    """Run the consolidated sales cleaning pipeline for selected sheets."""
    repo = repo_root()
    default_workbook = repo / "data" / "raw" / "synosales_2023.1-2024.12.xlsx"
    workbook = Path(os.environ.get("SYNOSALES_WORKBOOK", default_workbook))

    sheet_list = os.environ.get("SALES_CLEAN_SHEETS", "2023-C2,2024-C2,2023,2024")
    include_sheets = [sheet.strip() for sheet in sheet_list.split(",") if sheet.strip()]

    config = SalesCleaningConfig(workbook_path=workbook, include_sheets=include_sheets)
    LOG.info("Running sales cleaning for %s on sheets %s", workbook, include_sheets)
    cleaned = run_sales_cleaning_pipeline(config)

    output_path = Path(
        os.environ.get(
            "SALES_CLEAN_OUTPUT",
            repo / "data" / "processed" / "synosales_cleaned.parquet",
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.info("Writing cleaned parquet to %s", output_path)
    cleaned.to_parquet(output_path, index=False)


# ---------------------------------------------------------------------------
# dbt helpers
# ---------------------------------------------------------------------------


def run_dbt(command: str) -> None:
    """Run a dbt CLI command inside the project directory."""
    repo = repo_root()
    dbt_dir = repo / "dbt"
    env = os.environ.copy()
    env.setdefault("DBT_PROFILES_DIR", str(dbt_dir))
    LOG.info("Executing dbt command: %s", command)
    subprocess.run(
        command,
        cwd=dbt_dir,
        shell=True,
        env=env,
        check=True,
    )


def dbt_run_select(target: str) -> None:
    run_dbt(f"dbt run --select {target}")


def dbt_test_select(target: str) -> None:
    run_dbt(f"dbt test --select {target}")


def dbt_seed(select: Optional[str] = None) -> None:
    command = "dbt seed"
    if select:
        command += f" --select {select}"
    run_dbt(command)


# ---------------------------------------------------------------------------
# Forecast/trend helpers
# ---------------------------------------------------------------------------


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_baseline_forecast(
    *,
    output_dir: Optional[Path] = None,
    file_glob: str = "*sales_history_*.csv",
    cohort: str = "baseline",
    extra_sources: Optional[Iterable[Path]] = None,
) -> None:
    """Run the existing regression baseline as a placeholder forecast."""
    repo = repo_root()
    artifacts_dir = ensure_directory(
        Path(output_dir) if output_dir else repo / "data" / "processed" / "forecasts"
    )
    LOG.info("Running baseline forecast for %s cohort into %s", cohort, artifacts_dir)
    # Existing helper reads from data/processed using glob.
    train_regression_forecast(output_dir=artifacts_dir, file_glob=file_glob)
    if extra_sources:
        for src in extra_sources:
            LOG.info("Extra source considered for cohort %s: %s", cohort, src)


# ---------------------------------------------------------------------------
# Activation helpers
# ---------------------------------------------------------------------------


def trigger_metabase_refresh(**context: Dict[str, Any]) -> None:
    """Trigger Metabase dashboard refresh via n8n webhook if configured."""
    webhook = os.environ.get("N8N_METABASE_WEBHOOK")
    cohort = (
        context.get("dag_run").conf.get("cohort") if context.get("dag_run") else None
    )
    if not webhook:
        LOG.info(
            "Metabase webhook not configured; skipping refresh for cohort %s", cohort
        )
        return

    LOG.info("Triggering Metabase refresh via webhook for cohort %s", cohort)
    subprocess.run(
        ["curl", "-sf", "-X", "POST", webhook],
        env=os.environ.copy(),
        check=True,
    )


def log_activation_summary(**context: Dict[str, Any]) -> None:
    """Emit a simple log summarizing the activation payload."""
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run else {}
    LOG.info("Activation summary payload: %s", conf)


# ---------------------------------------------------------------------------
# Common DAG default args
# ---------------------------------------------------------------------------


def default_dag_args() -> Dict[str, Any]:
    """Standard default args shared by all DAGs."""
    return {
        "owner": "bi_platform",
        "depends_on_past": False,
        "email_on_failure": True,
        "email": [
            email.strip()
            for email in os.environ.get("PIPELINE_ALERT_RECIPIENTS", "").split(",")
            if email.strip()
        ],
        "retries": int(os.environ.get("AIRFLOW_TASK_RETRIES", "1")),
        "retry_delay": timedelta(
            minutes=int(os.environ.get("AIRFLOW_RETRY_DELAY_MIN", "15"))
        ),
    }
