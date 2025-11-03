"""Utilities for shaping cleaned sales data into quarterly training sets."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

DEFAULT_DATE_CANDIDATES: tuple[str, ...] = (
    "invoice_date",
    "Invoice Date",
    "PI Date",
    "Date",
    "sale_date",
    "OrderDate",
    "order_date",
)

DEFAULT_FOCUS_PRODUCTS: tuple[str, ...] = (
    "SVR-DT-DS-T1",
    "SVR-DT-DS-T2",
    "SVR-DT-DS-T3",
)
FOCUS_ENV_VAR = "SYNOBI_FORECAST_PRODUCTS"
FOCUS_FLAG_COLUMN = "is_focus_product"


def _repo_root() -> Path:
    """Resolve the project root from env or current file location."""
    env_root = os.environ.get("SYNOBI_REPO_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[2]


def load_clean_sales(parquet_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the cleaned Synology sales snapshot from disk."""
    resolved = Path(parquet_path) if parquet_path else _repo_root() / "data" / "processed" / "synosales_cleaned.parquet"
    if not resolved.exists():
        raise FileNotFoundError(f"Cleaned sales parquet not found: {resolved}")
    return pd.read_parquet(resolved)


def _resolve_sale_date(df: pd.DataFrame, date_candidates: Sequence[str]) -> pd.Series:
    """Find a usable date column and return a normalized datetime series."""
    for column in date_candidates:
        if column in df.columns:
            series = pd.to_datetime(df[column], errors="coerce")
            if series.notna().any():
                return series
    raise ValueError(
        "No supported date column found. Provide one of: "
        f"{', '.join(date_candidates)}. Available columns: {', '.join(df.columns)}"
    )


def prepare_quarterly_dataset(
    df: pd.DataFrame,
    *,
    value_column: str = "usd_adjusted_total",
    segment_columns: Optional[Sequence[str]] = None,
    date_candidates: Sequence[str] = DEFAULT_DATE_CANDIDATES,
) -> pd.DataFrame:
    """Aggregate cleaned sales data to quarter totals per segment."""
    working = df.copy()
    working["sale_date"] = _resolve_sale_date(working, date_candidates)
    working = working.dropna(subset=["sale_date"])
    working["sale_quarter"] = working["sale_date"].dt.to_period("Q")

    if value_column not in working.columns:
        raise ValueError(f"Value column '{value_column}' not present in dataframe.")

    working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0.0)

    segment_columns = tuple(segment_columns or ())
    for column in segment_columns:
        if column not in working.columns:
            raise ValueError(f"Segment column '{column}' not present in dataframe.")
        working[column] = working[column].fillna("Unknown")

    group_fields = list(segment_columns) + ["sale_quarter"]
    aggregated = (
        working.groupby(group_fields, dropna=False)[value_column]
        .sum()
        .reset_index()
        .rename(columns={value_column: "quarter_total"})
    )

    aggregated = _expand_missing_quarters(aggregated, segment_columns)

    aggregated["quarter_start"] = aggregated["sale_quarter"].dt.to_timestamp(how="start")
    aggregated["quarter_end"] = aggregated["sale_quarter"].dt.to_timestamp(how="end")
    aggregated["quarter_total"] = aggregated["quarter_total"].astype(float)
    return aggregated.sort_values(group_fields).reset_index(drop=True)


def _expand_missing_quarters(df: pd.DataFrame, segment_columns: Sequence[str]) -> pd.DataFrame:
    """Ensure every segment has contiguous quarters between first and last observation."""
    if df.empty:
        return df

    quarter_range = pd.period_range(df["sale_quarter"].min(), df["sale_quarter"].max(), freq="Q")

    if segment_columns:
        segment_levels = [df[col].unique() for col in segment_columns]
        full_index = pd.MultiIndex.from_product(
            [*segment_levels, quarter_range], names=[*segment_columns, "sale_quarter"]
        )
        reindexed = (
            df.set_index([*segment_columns, "sale_quarter"])
            .reindex(full_index, fill_value=0.0)
            .reset_index()
        )
    else:
        full_index = pd.Index(quarter_range, name="sale_quarter")
        reindexed = df.set_index("sale_quarter").reindex(full_index, fill_value=0.0).reset_index()

    return reindexed


def _resolve_focus_products() -> tuple[str, ...]:
    """Resolve focus products from environment or fallback defaults."""
    env_value = os.environ.get(FOCUS_ENV_VAR, "")
    if env_value:
        tokens = [token.strip() for token in env_value.split(",")]
        filtered = tuple(token for token in tokens if token)
        if filtered:
            return filtered
    return DEFAULT_FOCUS_PRODUCTS


def tag_focus_products(
    df: pd.DataFrame,
    *,
    product_column: str = "Product",
    focus_products: Optional[Sequence[str]] = None,
    focus_flag_column: str = FOCUS_FLAG_COLUMN,
) -> pd.DataFrame:
    """Return a copy of ``df`` with a boolean focus flag column added."""
    if product_column not in df.columns:
        raise ValueError(f"Product column '{product_column}' not present in dataframe.")

    focus_list = tuple(focus_products) if focus_products is not None else _resolve_focus_products()
    if not focus_list:
        raise ValueError("Focus product list is empty; provide at least one product identifier.")

    tagged = df.copy()
    tagged[focus_flag_column] = tagged[product_column].isin(focus_list)
    return tagged


def split_latest_quarter(
    quarterly_df: pd.DataFrame,
    *,
    quarter_column: str = "sale_quarter",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Period]:
    """Split quarterly aggregates into historical training data and the latest quarter."""
    if quarterly_df.empty:
        raise ValueError("Quarterly dataframe is empty; cannot perform split.")

    if quarter_column not in quarterly_df.columns:
        raise ValueError(f"Quarter column '{quarter_column}' not present in dataframe.")

    latest_quarter = quarterly_df[quarter_column].max()
    train = quarterly_df[quarterly_df[quarter_column] < latest_quarter].reset_index(drop=True)
    test = quarterly_df[quarterly_df[quarter_column] == latest_quarter].reset_index(drop=True)

    if train.empty or test.empty:
        raise ValueError("Insufficient quarters to create both train and test splits.")

    return train, test, latest_quarter


def prepare_quarterly_views(
    df: pd.DataFrame,
    *,
    value_column: str = "usd_adjusted_total",
    segment_columns: Optional[Sequence[str]] = None,
    date_candidates: Sequence[str] = DEFAULT_DATE_CANDIDATES,
    product_column: str = "Product",
    focus_products: Optional[Sequence[str]] = None,
    focus_flag_column: str = FOCUS_FLAG_COLUMN,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (global, focus-only) quarterly aggregations."""
    tagged = tag_focus_products(
        df,
        product_column=product_column,
        focus_products=focus_products,
        focus_flag_column=focus_flag_column,
    )

    base_segments = tuple(segment_columns or ())
    if focus_flag_column not in base_segments:
        segments_with_flag = base_segments + (focus_flag_column,)
    else:
        segments_with_flag = base_segments

    global_quarterly = prepare_quarterly_dataset(
        tagged,
        value_column=value_column,
        segment_columns=segments_with_flag,
        date_candidates=date_candidates,
    )

    focus_only = tagged[tagged[focus_flag_column]]
    if focus_only.empty:
        raise ValueError(
            "No rows matched the configured focus products. "
            "Verify the product identifiers or adjust the focus list."
        )

    focus_quarterly = prepare_quarterly_dataset(
        focus_only,
        value_column=value_column,
        segment_columns=segments_with_flag,
        date_candidates=date_candidates,
    )

    return global_quarterly, focus_quarterly


def build_quarterly_training_frames(
    parquet_path: Optional[Path] = None,
    *,
    value_column: str = "usd_adjusted_total",
    segment_columns: Optional[Sequence[str]] = None,
    date_candidates: Sequence[str] = DEFAULT_DATE_CANDIDATES,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Period]:
    """Convenience wrapper that loads data, aggregates to quarters, and returns train/test splits."""
    raw = load_clean_sales(parquet_path)
    quarterly = prepare_quarterly_dataset(
        raw,
        value_column=value_column,
        segment_columns=segment_columns,
        date_candidates=date_candidates,
    )
    return split_latest_quarter(quarterly)


def build_focus_quarterly_training_frames(
    parquet_path: Optional[Path] = None,
    *,
    value_column: str = "usd_adjusted_total",
    segment_columns: Optional[Sequence[str]] = None,
    date_candidates: Sequence[str] = DEFAULT_DATE_CANDIDATES,
    product_column: str = "Product",
    focus_products: Optional[Sequence[str]] = None,
    focus_flag_column: str = FOCUS_FLAG_COLUMN,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Period]:
    """Load data, aggregate to focus-product quarters, and return train/test splits."""
    raw = load_clean_sales(parquet_path)
    _, focus_quarterly = prepare_quarterly_views(
        raw,
        value_column=value_column,
        segment_columns=segment_columns,
        date_candidates=date_candidates,
        product_column=product_column,
        focus_products=focus_products,
        focus_flag_column=focus_flag_column,
    )
    return split_latest_quarter(focus_quarterly)
