"""End-to-end cleaning pipeline for the Synology multi-sheet sales workbook."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence

import pandas as pd

from .product_classification import assign_product_categories, attach_drive_capacity

DEFAULT_EXCHANGE_RATES: Dict[str, float] = {
    "AUD": 0.63,
    "EUR": 1.05,
    "JPY": 0.0067,
    "TWD": 0.031,
    "USD": 1.00,
}

DEFAULT_COUNTRY_MAPPING_PATH = Path(
    "data/mapping_table/Mapped_Countries_with_Regions.csv"
)
DEFAULT_DEVICE_BAY_MAPPING_PATH = Path("data/mapping_table/device_to_bay.csv")


@dataclass
class SalesCleaningConfig:
    """Configuration for :func:`run_sales_cleaning_pipeline`."""

    workbook_path: Path
    currency_rates: Mapping[str, float] = field(
        default_factory=lambda: DEFAULT_EXCHANGE_RATES
    )
    country_mapping_path: Path | None = None
    device_to_bay_path: Path | None = None
    engine: str | None = None
    include_sheets: Sequence[str] | None = None


def _load_workbook(
    workbook_path: Path,
    engine: str | None = None,
    include_sheets: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load and concatenate every worksheet from ``workbook_path``."""

    if not workbook_path.exists():
        raise FileNotFoundError(f"Source workbook not found: {workbook_path}")

    with pd.ExcelFile(workbook_path, engine=engine) as excel_file:
        sheet_names = list(excel_file.sheet_names)

    if include_sheets:
        requested = [sheet for sheet in include_sheets if sheet in sheet_names]
        missing = set(include_sheets) - set(requested)
        if missing:
            raise ValueError(
                f"Sheets not found in workbook {workbook_path}: {', '.join(sorted(missing))}"
            )
        sheet_names = requested

    frames = []
    for sheet_name in sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, engine=engine)
        frame["source_sheet"] = sheet_name
        frames.append(frame)

    if not frames:
        raise ValueError(f"No worksheets discovered in {workbook_path}")

    return pd.concat(frames, ignore_index=True, sort=False)


def _strip_parenthetical_products(frame: pd.DataFrame) -> pd.Series:
    """Remove leading parenthesised prefixes from the ``Product`` column."""

    products = frame["Product"].astype("string")
    return products.str.replace(r"^\([^)]*\)\s*", "", regex=True)


def _apply_currency_conversion(
    frame: pd.DataFrame, currency_rates: Mapping[str, float]
) -> pd.DataFrame:
    """Append USD conversion columns."""

    rate_frame = pd.DataFrame(
        {
            "Currency": list(currency_rates.keys()),
            "exchange_rate_to_usd": list(currency_rates.values()),
        }
    )
    merged = frame.merge(rate_frame, on="Currency", how="left")

    merged["usd_adjusted_price"] = merged["Price"] * merged["exchange_rate_to_usd"]
    merged["usd_adjusted_total"] = merged["Total"] * merged["exchange_rate_to_usd"]
    return merged


def _map_country_regions(
    frame: pd.DataFrame, mapping_path: Path | None
) -> pd.DataFrame:
    """Attach region metadata if a mapping file is provided."""

    if mapping_path is None:
        return frame

    if not mapping_path.exists():
        raise FileNotFoundError(f"Country mapping not found: {mapping_path}")

    mapping = pd.read_csv(mapping_path)
    if "Country" not in mapping.columns or "Region" not in mapping.columns:
        raise ValueError("Country mapping must include 'Country' and 'Region' columns")

    return frame.merge(mapping, on="Country", how="left")


def _attach_device_bays(
    frame: pd.DataFrame, device_bay_path: Path | None
) -> pd.DataFrame:
    """Attach bay counts when a reference table is available."""

    if device_bay_path is None:
        return frame

    if not device_bay_path.exists():
        raise FileNotFoundError(f"Device-to-bay mapping not found: {device_bay_path}")

    bay_map = pd.read_csv(device_bay_path)
    if "Product" not in bay_map.columns or "Bays" not in bay_map.columns:
        raise ValueError("Device bay mapping must include 'Product' and 'Bays'")

    merged = frame.merge(bay_map, on="Product", how="left")
    merged["total_bays"] = merged["Bays"] * merged["Quantity"]
    return merged


def _clean_sales_frame(config: SalesCleaningConfig) -> pd.DataFrame:
    """Internal helper performing the full cleaning sequence."""

    frame = _load_workbook(
        config.workbook_path,
        config.engine,
        include_sheets=config.include_sheets,
    )

    frame = frame.rename(columns=str.strip)
    frame = frame[frame["Total"] >= 0].copy()
    frame.loc[:, "Product"] = _strip_parenthetical_products(frame)

    frame = assign_product_categories(
        frame, product_column="Product", type_column="Type", subtype_column="sub_cat"
    )
    frame = _apply_currency_conversion(frame, config.currency_rates)
    frame.loc[:, "Year"] = pd.to_datetime(frame["InvDate"], errors="coerce").dt.year

    country_map_path = config.country_mapping_path
    if country_map_path is None and DEFAULT_COUNTRY_MAPPING_PATH.exists():
        country_map_path = DEFAULT_COUNTRY_MAPPING_PATH
    frame = _map_country_regions(frame, country_map_path)

    frame = attach_drive_capacity(frame)
    device_bay_path = config.device_to_bay_path
    if device_bay_path is None and DEFAULT_DEVICE_BAY_MAPPING_PATH.exists():
        device_bay_path = DEFAULT_DEVICE_BAY_MAPPING_PATH
    frame = _attach_device_bays(frame, device_bay_path)

    return frame


def run_sales_cleaning_pipeline(config: SalesCleaningConfig) -> pd.DataFrame:
    """Execute the pipeline and return the cleaned DataFrame."""

    return _clean_sales_frame(config)


def parse_args(args: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workbook",
        type=Path,
        help="Path to the raw Synology sales workbook (e.g. data/raw/synosales_*.xlsx)",
    )
    parser.add_argument(
        "--country-map",
        type=Path,
        dest="country_map",
        help=(
            "Optional CSV with Country -> Region columns. "
            "Defaults to data/mapping_table/Mapped_Countries_with_Regions.csv when present."
        ),
    )
    parser.add_argument(
        "--device-bay-map",
        type=Path,
        dest="device_bay_map",
        help=(
            "Optional CSV with Product -> Bays columns. "
            "Defaults to data/mapping_table/device_to_bay.csv when present."
        ),
    )
    parser.add_argument(
        "--engine",
        dest="engine",
        help="Optional pandas Excel reader engine",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        dest="output",
        help="Optional path where the cleaned parquet file should be written",
    )
    parser.add_argument(
        "--sheet",
        dest="sheets",
        action="append",
        help=(
            "Limit processing to specific worksheet names. "
            "Add the flag multiple times for multiple sheets."
        ),
    )
    return parser.parse_args(args=args)


def main(cli_args: Iterable[str] | None = None) -> None:
    args = parse_args(cli_args)
    config = SalesCleaningConfig(
        workbook_path=args.workbook,
        country_mapping_path=args.country_map,
        device_to_bay_path=args.device_bay_map,
        engine=args.engine,
        include_sheets=args.sheets,
    )

    cleaned = run_sales_cleaning_pipeline(config)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_parquet(args.output, index=False)
        print(f"Cleaned dataset written to {args.output}")
    else:
        print(cleaned.head())


if __name__ == "__main__":
    main()
