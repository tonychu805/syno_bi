from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion import excel_to_dataframes


def test_save_dataframes_handles_name_collisions(tmp_path: Path) -> None:
    workbook = tmp_path / "workbook.xlsx"
    sheet_a = pd.DataFrame({"Month": ["2024/01"], "Quantity": [10]})
    sheet_b = pd.DataFrame({"Month": ["2024/02"], "Quantity": [12]})

    with pd.ExcelWriter(workbook) as writer:
        sheet_a.to_excel(writer, sheet_name="Sales History 2023", index=False)
        sheet_b.to_excel(writer, sheet_name="Sales History 2023!!!", index=False)

    saved_paths = excel_to_dataframes.load_and_save_excel_tabs(
        excel_path=workbook,
        output_dir=tmp_path,
        fmt="csv",
    )

    primary = saved_paths["Sales History 2023"]
    secondary = saved_paths["Sales History 2023!!!"]

    assert primary.name.endswith("sales_history_2023.csv")
    assert secondary.name.endswith("sales_history_2023_2.csv")

    saved_primary = pd.read_csv(primary)
    saved_secondary = pd.read_csv(secondary)

    pd.testing.assert_frame_equal(saved_primary, sheet_a)
    pd.testing.assert_frame_equal(saved_secondary, sheet_b)
