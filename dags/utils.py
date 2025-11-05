"""Shared helpers for Synology BI Airflow DAGs."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import timedelta
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from airflow.datasets import Dataset
from airflow.utils.log.logging_mixin import LoggingMixin

from src.forecasting.regression import train_regression_forecast
from src.forecasting.sarimax import (
    DEFAULT_PRESERVED_COLUMNS as DEFAULT_SARIMAX_COLUMNS,
)
from src.forecasting.sarimax import train_sarimax_forecast
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

    columns_of_interest = [
        col
        for col in (
            "PI",
            "Customer",
            "ItemCode",
            "Product",
            "Quantity",
            "usd_adjusted_price",
            "usd_adjusted_total",
            "InvDate",
            "Country",
            "Type",
            "sub_cat",
            "Year",
            "Region",
        )
        if col in cleaned.columns
    ]

    def export_parquet(frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        LOG.info("Writing cleaned parquet to %s", path)
        frame.loc[:, columns_of_interest].to_parquet(path, index=False)

    output_path = Path(
        os.environ.get(
            "SALES_CLEAN_OUTPUT",
            repo / "data" / "processed" / "synosales_cleaned.parquet",
        )
    )
    export_parquet(cleaned, output_path)

    source_column = "source_sheet" if "source_sheet" in cleaned.columns else None
    if source_column:
        suite_definitions = {
            "suite_a": os.environ.get(
                "SALES_SUITE_A_SHEETS", "2023,2024"
            ).split(","),
            "suite_b": os.environ.get(
                "SALES_SUITE_B_SHEETS", "2023-C2,2024-C2"
            ).split(","),
        }
        for suite_name, raw_values in suite_definitions.items():
            channels = [value.strip() for value in raw_values if value.strip()]
            suite_frame = cleaned[cleaned[source_column].isin(channels)].copy()
            if suite_frame.empty:
                LOG.warning(
                    "No rows matched channels %s for %s; skipping parquet output.",
                    channels,
                    suite_name,
                )
                continue

            suite_env_key = f"SALES_CLEAN_OUTPUT_{suite_name.upper()}"
            suite_path = Path(
                os.environ.get(
                    suite_env_key,
                    output_path.parent
                    / f"{output_path.stem}_{suite_name}{output_path.suffix}",
                )
            )
            export_parquet(suite_frame, suite_path)


# ---------------------------------------------------------------------------
# dbt helpers
# ---------------------------------------------------------------------------


def run_dbt(command: str) -> None:
    """Run a dbt CLI command inside the project directory."""
    repo = repo_root()
    dbt_dir = repo / "dbt"
    env = os.environ.copy()
    env.setdefault("DBT_PROFILES_DIR", str(dbt_dir))

    if "DBT_TARGET_PATH_OVERRIDE" in env:
        target_path = Path(env["DBT_TARGET_PATH_OVERRIDE"])
        env["DBT_TARGET_PATH"] = env["DBT_TARGET_PATH_OVERRIDE"]
    else:
        target_path = dbt_dir / "target_runtime"
        env.setdefault("DBT_TARGET_PATH", str(target_path))

    target_path.mkdir(parents=True, exist_ok=True)

    LOG.info("Executing dbt command: %s", command)
    subprocess.run(
        command,
        cwd=dbt_dir,
        shell=True,
        env=env,
        check=True,
    )


def cleanup_seed_relations(*, schema: str, relations: Iterable[str]) -> None:
    """Drop residual seed relations to avoid stale catalog entries."""
    relation_list = [relation for relation in relations if relation]
    if not relation_list:
        LOG.info("No seed relations requested for cleanup; skipping.")
        return

    args = json.dumps({"schema": schema, "relations": relation_list})
    quoted_args = shlex.quote(args)
    LOG.info(
        "Running dbt cleanup for schema %s with relations %s", schema, relation_list
    )
    run_dbt(
        f"dbt run-operation cleanup_seed_relations --args {quoted_args}"
    )


def dbt_run_select(target: str) -> None:
    run_dbt(f"dbt run --select {target}")


def dbt_test_select(target: str) -> None:
    run_dbt(f"dbt test --select {target}")


def dbt_seed(
    select: Optional[str] = None,
    *,
    cleanup_schema: str = "analytics_seeds",
    cleanup_relations: Optional[Iterable[str]] = None,
) -> None:
    command = "dbt seed"
    if cleanup_relations:
        cleanup_seed_relations(schema=cleanup_schema, relations=cleanup_relations)
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
    model_name: str = "baseline",
    include_sheets: Optional[Iterable[str]] = None,
    preserved_columns: Optional[Iterable[str]] = None,
) -> None:
    """Run the configured forecast pipeline for the requested cohort."""
    repo = repo_root()
    artifacts_dir = ensure_directory(
        Path(output_dir) if output_dir else repo / "data" / "processed" / "forecasts"
    )
    LOG.info(
        "Running %s forecast for %s cohort into %s", model_name, cohort, artifacts_dir
    )

    if model_name == "sarimax_svr_rm":
        sheet_list = (
            tuple(include_sheets)
            if include_sheets is not None
            else tuple(
                sheet.strip()
                for sheet in os.environ.get("SVR_RM_SHEETS", "2023,2024").split(",")
                if sheet.strip()
            )
        )
        column_list = (
            tuple(preserved_columns)
            if preserved_columns is not None
            else tuple(
                column.strip()
                for column in os.environ.get(
                    "SVR_RM_PRESERVE_COLUMNS",
                    ",".join(DEFAULT_SARIMAX_COLUMNS),
                ).split(",")
                if column.strip()
            )
        )
        result = train_sarimax_forecast(
            output_dir=artifacts_dir,
            cohort=cohort,
            model_name=model_name,
            include_sheets=sheet_list,
            preserved_columns=column_list,
        )
        LOG.info(
            "SARIMAX forecast for %s cohort persisted to %s",
            cohort,
            result.output_path,
        )
    else:
        # Existing helper reads from data/processed using glob.
        train_regression_forecast(output_dir=artifacts_dir, file_glob=file_glob)

    if extra_sources:
        for src in extra_sources:
            LOG.info("Extra source considered for cohort %s: %s", cohort, src)


def load_forecast_to_postgres(
    *,
    cohort: str,
    table: str = "forecast_overall",
    schema: str = "analytics",
    model_name: str = "baseline",
    model_version: str = "rolling_mean_v1",
) -> None:
    """Append the latest forecast CSV into the warehouse."""

    repo = repo_root()
    forecasts_dir = repo / "data" / "processed" / "forecasts"
    pattern = f"{model_name}_forecast_*.csv"
    csv_paths = sorted(forecasts_dir.glob(pattern))
    if not csv_paths:
        LOG.warning("No forecast CSVs found in %s; skipping load.", forecasts_dir)
        return

    latest_csv = csv_paths[-1]
    run_id = latest_csv.stem.replace(f"{model_name}_forecast_", "")
    LOG.info(
        "Loading forecast run %s from %s into %s.%s",
        run_id,
        latest_csv,
        schema,
        table,
    )

    df = pd.read_csv(latest_csv)
    if df.empty:
        LOG.warning("Forecast CSV %s is empty; skipping load.", latest_csv)
        return

    df["forecast_run_id"] = run_id
    df["cohort"] = cohort
    df["model_name"] = model_name
    df["model_version"] = model_version
    df["forecast_date"] = pd.to_datetime(df.get("forecast_date"), errors="coerce")
    df["forecast_quantity"] = pd.to_numeric(
        df.get("forecast_quantity"), errors="coerce"
    )
    df["forecast_revenue"] = pd.to_numeric(
        df.get("forecast_revenue"), errors="coerce"
    )
    for bound_column in ("forecast_revenue_lower", "forecast_revenue_upper"):
        if bound_column not in df.columns:
            df[bound_column] = pd.NA
        df[bound_column] = pd.to_numeric(df.get(bound_column), errors="coerce")
    df["sale_month"] = df["forecast_date"].dt.to_period("M").dt.to_timestamp("M")
    df["created_at"] = pd.Timestamp.now(tz="UTC")
    df = df.dropna(subset=["forecast_date"])

    cleaned_path = repo / "data" / "processed" / "synosales_cleaned.parquet"
    product_columns = {
        "product_name": "Product",
        "product_type": "Type",
        "product_subcategory": "sub_cat",
    }
    actual_columns = None
    if cleaned_path.exists():
        try:
            cleaned = pd.read_parquet(cleaned_path)
            cleaned["InvDate"] = pd.to_datetime(cleaned["InvDate"], errors="coerce")
            cleaned = cleaned.dropna(subset=["InvDate"])
            cleaned["sale_month"] = cleaned["InvDate"].dt.to_period("M").dt.to_timestamp("M")
            cleaned["channel"] = cleaned.get("source_sheet", pd.Series(index=cleaned.index, dtype="object")).fillna("synology_sales")
            sku_series = cleaned.get("ItemCode").astype("string").str.strip()
            product_series = cleaned.get("Product").astype("string").str.strip()
            cleaned["sku"] = sku_series.fillna(product_series).fillna("UNSPECIFIED")
            revenue_field = "usd_adjusted_total" if "usd_adjusted_total" in cleaned.columns else "Total"
            aggregated = (
                cleaned.groupby(["sale_month", "channel", "sku"], dropna=False)
                .agg(
                    actual_quantity=("Quantity", "sum"),
                    actual_revenue=(revenue_field, "sum"),
                    **{
                        name: (col, "first")
                        for name, col in product_columns.items()
                        if col in cleaned.columns
                    },
                )
                .reset_index()
            )
            actual_columns = aggregated
        except (ValueError, FileNotFoundError, OSError, SQLAlchemyError) as exc:
            LOG.warning("Unable to enrich forecast with actuals: %s", exc)

    if actual_columns is not None:
        df = df.merge(
            actual_columns,
            how="left",
            left_on=["sale_month", "channel", "sku"],
            right_on=["sale_month", "channel", "sku"],
        )
    else:
        df["actual_quantity"] = pd.NA
        df["actual_revenue"] = pd.NA
        for name in product_columns:
            df[name] = pd.NA

    df["actual_quantity"] = pd.to_numeric(df.get("actual_quantity"), errors="coerce")
    df["actual_revenue"] = pd.to_numeric(df.get("actual_revenue"), errors="coerce")

    for display, column in product_columns.items():
        if display not in df.columns:
            df[display] = pd.NA

    df["forecast_date"] = pd.to_datetime(df["forecast_date"], errors="coerce").dt.date
    df["sale_month"] = pd.to_datetime(df.get("sale_month"), errors="coerce")
    df["sale_month"] = df["sale_month"].dt.to_period("M").dt.to_timestamp("M").dt.date

    columns = [
        "forecast_run_id",
        "cohort",
        "model_name",
        "model_version",
        "sku",
        "channel",
        "sale_month",
        "forecast_date",
        "forecast_quantity",
        "forecast_revenue",
        "actual_quantity",
        "actual_revenue",
        "product_name",
        "product_type",
        "product_subcategory",
        "forecast_revenue_lower",
        "forecast_revenue_upper",
        "created_at",
    ]
    df = df.reindex(columns=columns)

    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ.get("WAREHOUSE_USER", "admin"),
        password=os.environ.get("WAREHOUSE_PASSWORD", "Black17998~"),
        host=os.environ.get("WAREHOUSE_HOST", "postgres"),
        port=int(os.environ.get("WAREHOUSE_PORT", "5432")),
        database=os.environ.get("WAREHOUSE_DB", "syno_bi"),
    )
    engine = create_engine(connection_url)

    create_schema_stmt = text(f"create schema if not exists {schema}")
    create_table_stmt = text(
        f"""
        create table if not exists {schema}.{table} (
            forecast_run_id text not null,
            cohort text not null,
            model_name text not null,
            model_version text not null,
            sku text,
            channel text,
            sale_month date,
            forecast_date date,
            forecast_quantity numeric,
            forecast_revenue numeric,
            actual_quantity numeric,
            actual_revenue numeric,
            product_name text,
            product_type text,
            product_subcategory text,
            forecast_revenue_lower numeric,
            forecast_revenue_upper numeric,
            created_at timestamptz not null default now()
        )
        """
    )

    delete_stmt = text(
        f"""
        delete from {schema}.{table}
        where cohort = :cohort
          and model_name = :model_name
          and model_version = :model_version
        """
    )

    add_column_statements = [
        f"alter table {schema}.{table} add column if not exists sale_month date",
        f"alter table {schema}.{table} add column if not exists actual_quantity numeric",
        f"alter table {schema}.{table} add column if not exists actual_revenue numeric",
        f"alter table {schema}.{table} add column if not exists product_name text",
        f"alter table {schema}.{table} add column if not exists product_type text",
        f"alter table {schema}.{table} add column if not exists product_subcategory text",
        f"alter table {schema}.{table} add column if not exists forecast_revenue_lower numeric",
        f"alter table {schema}.{table} add column if not exists forecast_revenue_upper numeric",
    ]

    with engine.begin() as conn:
        conn.execute(create_schema_stmt)
        conn.execute(create_table_stmt)
        for statement in add_column_statements:
            conn.execute(text(statement))
        conn.execute(
            delete_stmt,
            {
                "cohort": cohort,
                "model_name": model_name,
                "model_version": model_version,
            },
        )
        df.to_sql(
            table,
            conn,
            schema=schema,
            if_exists="append",
            index=False,
            method="multi",
        )

    LOG.info(
        "Forecast run %s (%s/%s) loaded into %s.%s",
        run_id,
        model_name,
        model_version,
        schema,
        table,
    )


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
