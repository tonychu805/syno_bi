"""SARIMAX-based forecasting utilities for SVR-RM cohorts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .preprocessing import load_clean_sales
from .regression import FORECAST_HOLDOUT_START, FORECAST_HORIZON_MONTHS


DEFAULT_SVR_RM_SHEETS: tuple[str, ...] = ("2023", "2024")
DEFAULT_PRESERVED_COLUMNS: tuple[str, ...] = (
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


LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class SarimaxForecastResult:
    """Container for the forecast artefacts and metadata."""

    forecast: pd.DataFrame
    output_path: Path
    combined: pd.DataFrame | None = None
    combined_output_path: Path | None = None
    metrics: dict[str, float] | None = None
    metrics_path: Path | None = None


def _ensure_sequence(
    arg: Iterable[str] | None, *, default: Sequence[str]
) -> tuple[str, ...]:
    if arg is None:
        return tuple(default)
    return tuple(item for item in arg if item)


def _prepare_monthly_series(
    data: pd.DataFrame,
    *,
    holdout_start: pd.Timestamp,
) -> tuple[pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    """Return monthly series split by holdout boundary along with full aggregates."""

    working = data.copy()
    working["InvDate"] = pd.to_datetime(working["InvDate"], errors="coerce")
    working = working.dropna(subset=["InvDate"])
    working["usd_adjusted_total"] = pd.to_numeric(
        working["usd_adjusted_total"], errors="coerce"
    )
    working["Quantity"] = pd.to_numeric(working["Quantity"], errors="coerce")

    monthly = (
        working.groupby(pd.Grouper(key="InvDate", freq="M"))
        .agg(
            revenue=("usd_adjusted_total", "sum"),
            quantity=("Quantity", "sum"),
        )
        .sort_index()
    )

    if monthly.empty:
        raise ValueError("No monthly aggregates available for SARIMAX training.")

    history = monthly.loc[monthly.index < holdout_start]
    if history.empty:
        raise ValueError(
            f"No observations available prior to holdout boundary {holdout_start.date()}"
        )

    return (
        history["revenue"],
        history["quantity"],
        monthly,
        monthly.loc[monthly.index >= holdout_start],
    )


def _fit_sarimax(series: pd.Series) -> SARIMAX:
    return SARIMAX(
        series,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 12),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )


def train_sarimax_forecast(
    *,
    output_dir: Path,
    cohort: str,
    model_name: str = "sarimax",
    include_sheets: Iterable[str] | None = None,
    preserved_columns: Iterable[str] | None = None,
    holdout_start: pd.Timestamp = FORECAST_HOLDOUT_START,
    horizon_months: int = FORECAST_HORIZON_MONTHS,
    confidence_alpha: float = 0.05,
) -> SarimaxForecastResult:
    """Train a SARIMAX model on SVR-RM revenue and persist forecast artefacts."""

    sheets = _ensure_sequence(include_sheets, default=DEFAULT_SVR_RM_SHEETS)
    columns = _ensure_sequence(preserved_columns, default=DEFAULT_PRESERVED_COLUMNS)

    sales = load_clean_sales()
    if "source_sheet" in sales.columns:
        sales = sales[sales["source_sheet"].isin(sheets)]

    prefix = os.environ.get("SVR_RM_SUBCAT_PREFIX", "SVR-RM").strip()
    if prefix and "sub_cat" in sales.columns:
        sales = sales[
            sales["sub_cat"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.startswith(prefix.upper())
        ]

    missing_columns = [column for column in columns if column not in sales.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns for SARIMAX forecast: {', '.join(missing_columns)}"
        )
    if sales.empty:
        raise ValueError(
            "No records available after applying sheet and cohort filters for SARIMAX."
        )

    working = sales.loc[:, list(columns)].copy()
    (
        revenue_history,
        quantity_history,
        monthly_aggregates,
        holdout_aggregates,
    ) = _prepare_monthly_series(working, holdout_start=holdout_start)

    # Revenue SARIMAX fit
    revenue_model = _fit_sarimax(revenue_history)
    revenue_fit = revenue_model.fit(disp=False)
    revenue_forecast = revenue_fit.get_forecast(steps=horizon_months)
    revenue_mean = revenue_forecast.predicted_mean
    revenue_conf = revenue_forecast.conf_int(alpha=confidence_alpha)

    # Quantity baseline: reuse rolling average if SARIMAX fails
    try:
        quantity_model = _fit_sarimax(quantity_history)
        quantity_fit = quantity_model.fit(disp=False)
        quantity_pred = quantity_fit.get_forecast(steps=horizon_months).predicted_mean
    except Exception:
        rolling_window = min(len(quantity_history), 3)
        fallback = quantity_history.tail(rolling_window).mean()
        quantity_pred = pd.Series(
            np.full(horizon_months, fallback, dtype=float),
            index=revenue_mean.index,
        )

    forecast_index = pd.to_datetime(revenue_mean.index)

    output = pd.DataFrame(
        {
            "sku": [f"{cohort.upper()}_ALL"] * horizon_months,
            "channel": [cohort] * horizon_months,
            "forecast_date": forecast_index,
            "forecast_quantity": quantity_pred.values,
            "forecast_revenue": revenue_mean.values,
            "forecast_revenue_lower": revenue_conf.iloc[:, 0].values,
            "forecast_revenue_upper": revenue_conf.iloc[:, 1].values,
        }
    )

    combined = monthly_aggregates.rename(
        columns={"revenue": "actual_revenue", "quantity": "actual_quantity"}
    ).copy()
    combined_index = combined.index.union(forecast_index)
    combined = combined.reindex(combined_index).sort_index()
    combined["forecast_quantity"] = np.nan
    combined["forecast_revenue"] = np.nan
    combined["forecast_revenue_lower"] = np.nan
    combined["forecast_revenue_upper"] = np.nan
    combined["forecast_date"] = combined.index
    combined.loc[forecast_index, "forecast_quantity"] = quantity_pred.values
    combined.loc[forecast_index, "forecast_revenue"] = revenue_mean.values
    combined.loc[forecast_index, "forecast_revenue_lower"] = revenue_conf.iloc[
        :, 0
    ].values
    combined.loc[forecast_index, "forecast_revenue_upper"] = revenue_conf.iloc[
        :, 1
    ].values
    combined["channel"] = cohort
    combined["sku"] = f"{cohort.upper()}_ALL"
    combined.index.name = "sale_month"

    combined_frame = combined.reset_index()
    combined_frame["sale_month"] = pd.to_datetime(
        combined_frame["sale_month"], errors="coerce"
    )
    combined_frame["forecast_date"] = pd.to_datetime(
        combined_frame["forecast_date"], errors="coerce"
    )

    metrics: dict[str, float] = {}
    evaluation_index = forecast_index.intersection(holdout_aggregates.index)
    if not evaluation_index.empty:
        actual_values = holdout_aggregates.loc[evaluation_index, "revenue"].to_numpy(
            dtype=float
        )
        predicted_values = revenue_mean.loc[evaluation_index].to_numpy(dtype=float)
        non_zero_mask = np.abs(actual_values) > 0
        if non_zero_mask.any():
            mape = (
                np.abs(actual_values[non_zero_mask] - predicted_values[non_zero_mask])
                / np.abs(actual_values[non_zero_mask])
            ).mean() * 100
            metrics["mape"] = float(mape)
            LOG.info("SVR-RM SARIMAX MAPE over holdout: %.2f%%", mape)
        else:
            LOG.warning(
                "Holdout actuals are zero-valued; skipping MAPE calculation for SVR-RM."
            )
    else:
        LOG.warning(
            "No overlapping holdout periods between actuals and forecasts; skipping MAPE."
        )

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{model_name}_forecast_{timestamp}.csv"
    output.to_csv(output_path, index=False)

    combined_output_path = output_dir / f"{model_name}_combined_{timestamp}.csv"
    combined_export = combined_frame.copy()
    combined_export["sale_month"] = combined_export["sale_month"].dt.date
    combined_export["forecast_date"] = combined_export["forecast_date"].dt.date
    combined_export.to_csv(combined_output_path, index=False)

    metrics_path: Path | None = None
    if metrics:
        metrics_path = output_dir / f"{model_name}_metrics_{timestamp}.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    return SarimaxForecastResult(
        forecast=output,
        output_path=output_path,
        combined=combined_frame,
        combined_output_path=combined_output_path,
        metrics=metrics or None,
        metrics_path=metrics_path,
    )
