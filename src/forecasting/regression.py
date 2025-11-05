"""Baseline forecasting utilities leveraging ingestion outputs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

FORECAST_HOLDOUT_START = pd.Timestamp(
    os.environ.get("FORECAST_HOLDOUT_START", "2024-10-01")
).tz_localize(None)
FORECAST_HORIZON_MONTHS = int(os.environ.get("FORECAST_HORIZON_MONTHS", "3"))
FORECAST_ROLLING_WINDOW = int(os.environ.get("FORECAST_ROLLING_WINDOW", "3"))


def _repo_root() -> Path:
    return Path(os.environ.get("SYNOBI_REPO_ROOT", Path(__file__).resolve().parents[2]))


def _processed_dir() -> Path:
    return _repo_root() / "data" / "processed"


def _cleaned_parquet_path() -> Path:
    return _repo_root() / "data" / "processed" / "synosales_cleaned.parquet"


def _load_sales_history_from_parquet(path: Path) -> pd.DataFrame:
    logger.info("Loading cleaned sales history from parquet: %s", path)
    frame = pd.read_parquet(path)

    working = frame.copy()
    if "sale_date" in working.columns:
        working["sale_date"] = pd.to_datetime(working["sale_date"], errors="coerce")
    elif "InvDate" in working.columns:
        working["sale_date"] = pd.to_datetime(working["InvDate"], errors="coerce")
    else:
        raise ValueError("Cleaned parquet is missing a sale date column (InvDate).")

    sku_series = None
    if "ItemCode" in working.columns:
        sku_series = working["ItemCode"].astype("string").str.strip()
    if "Product" in working.columns:
        product_series = working["Product"].astype("string").str.strip()
        sku_series = (
            sku_series.fillna(product_series)
            if sku_series is not None
            else product_series
        )
    if sku_series is None:
        raise ValueError(
            "Cleaned parquet is missing both ItemCode and Product columns."
        )

    if "source_sheet" in working.columns:
        channel_series = working["source_sheet"].astype("string").str.strip()
        channel_series = channel_series.fillna("synology_sales")
    else:
        channel_series = pd.Series("synology_sales", index=working.index)

    quantity = pd.to_numeric(working.get("Quantity"), errors="coerce").fillna(0.0)
    revenue_source = (
        working.get("usd_adjusted_total")
        if "usd_adjusted_total" in working.columns
        else working.get("Total")
    )
    if revenue_source is not None:
        revenue = pd.to_numeric(revenue_source, errors="coerce").fillna(0.0)
    else:
        revenue = pd.Series(0.0, index=working.index)

    tidy = pd.DataFrame(
        {
            "sale_date": working["sale_date"],
            "sku": sku_series.fillna("UNSPECIFIED").astype(str),
            "channel": channel_series.astype(str),
            "quantity": quantity,
            "revenue": revenue,
        }
    )

    tidy = tidy.dropna(subset=["sale_date"])
    return tidy


def _load_sales_history_from_csv(files: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in files:
        try:
            frame = pd.read_csv(path)
        except FileNotFoundError:
            logger.warning("Sales history file not found: %s", path)
            continue

        if frame.empty:
            continue

        channel = "IM" if "im_" in path.stem else "TDBS"
        frame = frame.copy()
        date_col = next(
            (
                col
                for col in ("Month", "Date", "Transaction Date")
                if col in frame.columns
            ),
            None,
        )
        sku_col = next(
            (col for col in ("Product", "SKU", "Sku") if col in frame.columns), None
        )
        qty_col = next(
            (
                col
                for col in ("Received Qty", "Quantity", "Qty")
                if col in frame.columns
            ),
            None,
        )
        revenue_col = next(
            (col for col in ("Total", "Revenue") if col in frame.columns), None
        )

        if not all([date_col, sku_col, qty_col]):
            logger.warning("Skipping %s; missing expected columns.", path.name)
            continue

        frame["sale_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        frame["sku"] = frame[sku_col].astype(str)
        frame["channel"] = channel
        frame["quantity"] = pd.to_numeric(frame[qty_col], errors="coerce").fillna(0.0)
        frame["revenue"] = (
            pd.to_numeric(frame[revenue_col], errors="coerce").fillna(0.0)
            if revenue_col
            else 0.0
        )

        frames.append(frame[["sale_date", "sku", "channel", "quantity", "revenue"]])

    if not frames:
        raise ValueError("No usable sales history files were found for forecasting.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["sale_date"])
    combined["quantity"] = combined["quantity"].clip(lower=0)
    return combined


def _load_sales_history(
    files: Iterable[Path], parquet_path: Optional[Path]
) -> pd.DataFrame:
    if parquet_path is not None and parquet_path.exists():
        return _load_sales_history_from_parquet(parquet_path)
    if parquet_path is not None:
        logger.warning(
            "Cleaned parquet not found at %s; falling back to CSV sales history.",
            parquet_path,
        )
    return _load_sales_history_from_csv(files)


def _normalize_month_end(timestamp: pd.Timestamp | datetime) -> pd.Timestamp:
    return pd.Timestamp(timestamp).to_period("M").to_timestamp("M")


def _prepare_monthly_history(sales_history: pd.DataFrame) -> pd.DataFrame:
    history = sales_history.copy()
    history["sale_month"] = history["sale_date"].apply(_normalize_month_end)
    monthly = (
        history.groupby(["sku", "channel", "sale_month"], as_index=False)
        .agg(quantity=("quantity", "sum"), revenue=("revenue", "sum"))
        .sort_values("sale_month")
    )
    return monthly


def _future_months(start: pd.Timestamp, horizon: int) -> List[pd.Timestamp]:
    base = _normalize_month_end(start)
    return [base + pd.offsets.MonthEnd(i + 1) for i in range(horizon)]


def _create_forecast_baseline(sales_history: pd.DataFrame) -> pd.DataFrame:
    monthly_history = _prepare_monthly_history(sales_history)
    if monthly_history.empty:
        raise ValueError("Sales history is empty; cannot compute baseline forecast.")

    cutoff = _normalize_month_end(FORECAST_HOLDOUT_START)
    train_history = monthly_history[monthly_history["sale_month"] < cutoff].copy()
    if train_history.empty:
        raise ValueError("No training data available before holdout start %s" % cutoff)

    future_months = _future_months(cutoff, FORECAST_HORIZON_MONTHS)
    forecasts = []

    for (sku, channel), history in train_history.groupby(["sku", "channel"]):
        history = history.sort_values("sale_month")
        if history.empty:
            continue
        last_month = _normalize_month_end(history["sale_month"].max())
        rolling_quantity = (
            history["quantity"]
            .rolling(window=FORECAST_ROLLING_WINDOW, min_periods=1)
            .mean()
        )
        rolling_revenue = (
            history["revenue"]
            .rolling(window=FORECAST_ROLLING_WINDOW, min_periods=1)
            .mean()
        )
        baseline_quantity = float(rolling_quantity.iloc[-1])
        baseline_revenue = float(rolling_revenue.iloc[-1])

        for forecast_date in future_months:
            if forecast_date > last_month:
                forecasts.append(
                    {
                        "sku": sku,
                        "channel": channel,
                        "forecast_date": forecast_date,
                        "forecast_quantity": baseline_quantity,
                        "forecast_revenue": baseline_revenue,
                    }
                )

    if not forecasts:
        raise ValueError(
            "Unable to derive forecasts; no eligible cohorts before holdout start."
        )

    return pd.DataFrame(forecasts)


def train_regression_forecast(
    output_dir: Path,
    sales_history_dir: Optional[Path] = None,
    file_glob: str = "*sales_history_*.csv",
) -> Path:
    """Generate a simple rolling-mean forecast and persist artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    history_dir = sales_history_dir or _processed_dir()
    files = sorted(Path(history_dir).glob(file_glob))

    parquet_env = os.environ.get("SALES_HISTORY_PARQUET")
    parquet_path = Path(parquet_env) if parquet_env else _cleaned_parquet_path()
    sales_history = _load_sales_history(
        files, parquet_path if parquet_path.exists() else None
    )

    forecasts = _create_forecast_baseline(sales_history)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    forecast_path = output_dir / f"baseline_forecast_{timestamp}.csv"
    metadata_path = output_dir / f"baseline_forecast_{timestamp}.json"

    forecasts.to_csv(forecast_path, index=False)

    metadata = {
        "generated_at": timestamp,
        "method": "rolling_mean_baseline",
        "rolling_window_months": FORECAST_ROLLING_WINDOW,
        "holdout_start": FORECAST_HOLDOUT_START.strftime("%Y-%m-%d"),
        "forecast_horizon_months": FORECAST_HORIZON_MONTHS,
        "source_files": [str(path) for path in files],
        "record_count": len(forecasts),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info("Baseline forecast saved to %s", forecast_path)
    return forecast_path
