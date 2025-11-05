"""SARIMAX-based forecasting utilities for SVR-RM cohorts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(slots=True)
class SarimaxForecastResult:
    """Container for the forecast artefact and metadata."""

    forecast: pd.DataFrame
    output_path: Path


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
) -> tuple[pd.Series, pd.Series]:
    """Return monthly revenue and quantity series split by holdout boundary."""

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

    missing_columns = [column for column in columns if column not in sales.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns for SARIMAX forecast: {', '.join(missing_columns)}"
        )

    working = sales.loc[:, list(columns)].copy()
    revenue_history, quantity_history = _prepare_monthly_series(
        working, holdout_start=holdout_start
    )

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

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{model_name}_forecast_{timestamp}.csv"
    output.to_csv(output_path, index=False)

    return SarimaxForecastResult(forecast=output, output_path=output_path)
