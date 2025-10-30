"""Utilities for converting multi-sheet Excel workbooks into persisted DataFrames.

This module focuses on reading the source workbook under ``raw/`` and storing each
worksheet as a serialized pandas DataFrame so downstream jobs can pick them up
without mutating the original inputs.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, Mapping

import pandas as pd

SUPPORTED_FORMATS = {"pickle", "csv"}


def sanitize_sheet_name(sheet_name: str) -> str:
    """Return a filesystem-safe representation of ``sheet_name``.

    The workbook already captures business-friendly labels, but those can contain
    spaces and punctuation that do not translate well to filenames. This helper
    normalises them to lowercase snake_case tokens.
    """

    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", sheet_name).strip("_")
    return cleaned.lower() or "worksheet"


def load_excel_tabs(excel_path: Path, *, engine: str | None = None) -> Dict[str, pd.DataFrame]:
    """Load every worksheet in ``excel_path`` into memory."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel workbook not found: {excel_path}")

    workbook = pd.ExcelFile(excel_path, engine=engine)
    return {sheet: workbook.parse(sheet_name=sheet) for sheet in workbook.sheet_names}


def save_dataframes(
    frames: Mapping[str, pd.DataFrame],
    output_dir: Path,
    *,
    fmt: str = "pickle",
    include_index: bool = False,
) -> Dict[str, Path]:
    """Persist every DataFrame to ``output_dir`` using the requested format."""

    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise ValueError(f"Unsupported format '{fmt}'. Supported formats: {supported}")

    output_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: Dict[str, Path] = {}
    name_counts: Dict[str, int] = {}
    for sheet_name, frame in frames.items():
        base_filename = sanitize_sheet_name(sheet_name)
        occurrence = name_counts.get(base_filename, 0)
        filename = base_filename if occurrence == 0 else f"{base_filename}_{occurrence + 1}"
        name_counts[base_filename] = occurrence + 1
        if fmt == "pickle":
            target = output_dir / f"{filename}.pkl"
            frame.to_pickle(target)
        else:
            target = output_dir / f"{filename}.csv"
            frame.to_csv(target, index=include_index)

        saved_paths[sheet_name] = target

    return saved_paths


def load_and_save_excel_tabs(
    excel_path: Path,
    output_dir: Path,
    *,
    fmt: str = "pickle",
    include_index: bool = False,
    engine: str | None = None,
) -> Dict[str, Path]:
    """Convenience wrapper that loads an Excel workbook and persists each sheet."""

    frames = load_excel_tabs(excel_path, engine=engine)
    return save_dataframes(frames, output_dir, fmt=fmt, include_index=include_index)


def parse_args(args: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "excel_path",
        type=Path,
        help="Path to the source Excel workbook (e.g. raw/synosales_2023.1-2024.12.xlsx)",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory where serialised DataFrames should be written",
    )
    parser.add_argument(
        "--format",
        "-f",
        dest="fmt",
        default="pickle",
        choices=sorted(SUPPORTED_FORMATS),
        help="Serialization format for the exported DataFrames",
    )
    parser.add_argument(
        "--include-index",
        dest="include_index",
        action="store_true",
        help="Persist the DataFrame index when exporting to CSV",
    )
    parser.add_argument(
        "--engine",
        dest="engine",
        help="Optional pandas Excel reader engine override (openpyxl, xlrd, etc.)",
    )
    return parser.parse_args(args=args)


def main(cli_args: Iterable[str] | None = None) -> None:
    args = parse_args(cli_args)
    saved_paths = load_and_save_excel_tabs(
        excel_path=args.excel_path,
        output_dir=args.output_dir,
        fmt=args.fmt,
        include_index=args.include_index,
        engine=args.engine,
    )

    for sheet_name, path in saved_paths.items():
        print(f"Saved '{sheet_name}' -> {path}")


if __name__ == "__main__":
    main()
