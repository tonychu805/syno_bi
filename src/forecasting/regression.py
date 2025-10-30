"""Baseline forecasting utilities leveraging ingestion outputs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _processed_dir() -> Path:
    repo_root = Path(os.environ.get("SYNOBI_REPO_ROOT", Path(__file__).resolve().parents[2]))
    return repo_root / "data" / "processed"


def _load_sales_history(files: Iterable[Path]) -> pd.DataFrame:
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
        date_col = next((col for col in ("Month", "Date", "Transaction Date") if col in frame.columns), None)
        sku_col = next((col for col in ("Product", "SKU", "Sku") if col in frame.columns), None)
        qty_col = next((col for col in ("Received Qty", "Quantity", "Qty") if col in frame.columns), None)
        revenue_col = next((col for col in ("Total", "Revenue") if col in frame.columns), None)

        if not all([date_col, sku_col, qty_col]):
            logger.warning("Skipping %s; missing expected columns.", path.name)
            continue

        frame["sale_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        frame["sku"] = frame[sku_col].astype(str)
        frame["channel"] = channel
        frame["quantity"] = pd.to_numeric(frame[qty_col], errors="coerce").fillna(0.0)
        frame["revenue"] = (
            pd.to_numeric(frame[revenue_col], errors="coerce").fillna(0.0) if revenue_col else 0.0
        )

        frames.append(frame[["sale_date", "sku", "channel", "quantity", "revenue"]])

    if not frames:
        raise ValueError("No usable sales history files were found for forecasting.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["sale_date"])
    return combined


def _create_forecast_baseline(sales_history: pd.DataFrame) -> pd.DataFrame:
    sales_history = sales_history.sort_values("sale_date")
    grouped = (
        sales_history.groupby(["sku", "channel", "sale_date"], as_index=False)
        .agg(quantity=("quantity", "sum"), revenue=("revenue", "sum"))
        .sort_values("sale_date")
    )

    grouped["rolling_quantity"] = (
        grouped.groupby(["sku", "channel"])["quantity"].transform(lambda s: s.rolling(window=3, min_periods=1).mean())
    )
    grouped["rolling_revenue"] = (
        grouped.groupby(["sku", "channel"])["revenue"].transform(lambda s: s.rolling(window=3, min_periods=1).mean())
    )

    forecasts = []
    for (sku, channel), history in grouped.groupby(["sku", "channel"]):
        history = history.sort_values("sale_date")
        if history.empty:
            continue
        next_date = history["sale_date"].max() + pd.offsets.MonthEnd(1)
        forecasts.append(
            {
                "sku": sku,
                "channel": channel,
                "forecast_date": next_date.normalize(),
                "forecast_quantity": float(history["rolling_quantity"].iloc[-1]),
                "forecast_revenue": float(history["rolling_revenue"].iloc[-1]),
            }
        )

    if not forecasts:
        raise ValueError("Unable to derive forecasts from the provided sales history.")

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
    sales_history = _load_sales_history(files)

    forecasts = _create_forecast_baseline(sales_history)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    forecast_path = output_dir / f"baseline_forecast_{timestamp}.csv"
    metadata_path = output_dir / f"baseline_forecast_{timestamp}.json"

    forecasts.to_csv(forecast_path, index=False)

    metadata = {
        "generated_at": timestamp,
        "method": "rolling_mean_baseline",
        "window": 3,
        "source_files": [str(path) for path in files],
        "record_count": len(forecasts),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info("Baseline forecast saved to %s", forecast_path)
    return forecast_path
