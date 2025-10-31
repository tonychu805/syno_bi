from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion import SalesCleaningConfig, run_sales_cleaning_pipeline


def _build_sample_workbook(path: Path) -> None:
    sheet_a = pd.DataFrame(
        {
            "Product": ["DS220j", "HAT5300-8T"],
            "Currency": ["USD", "USD"],
            "Price": [132.0, 200.0],
            "Total": [1056.0, 800.0],
            "Quantity": [8, 4],
            "InvDate": ["2021-01-04", "2021-05-06"],
            "Country": ["United States", "United States"],
        }
    )
    sheet_b = pd.DataFrame(
        {
            "Product": ["C2 Storage Advanced", "Adapter 65W_2"],
            "Currency": ["EUR", "EUR"],
            "Price": [18.2, 25.0],
            "Total": [18.2, 25.0],
            "Quantity": [1, 2],
            "InvDate": ["2022-02-01", "2022-02-02"],
            "Country": ["Germany", "Germany"],
        }
    )

    with pd.ExcelWriter(path) as writer:
        sheet_a.to_excel(writer, sheet_name="2021 Sales", index=False)
        sheet_b.to_excel(writer, sheet_name="2022 SaaS", index=False)


def test_pipeline_combines_and_enriches_workbook(tmp_path: Path) -> None:
    workbook = tmp_path / "synology.xlsx"
    _build_sample_workbook(workbook)

    country_map = tmp_path / "countries.csv"
    pd.DataFrame(
        {"Country": ["United States", "Germany"], "Region": ["NA", "DE"]}
    ).to_csv(country_map, index=False)

    device_map = tmp_path / "device_bays.csv"
    pd.DataFrame({"Product": ["DS220j"], "Bays": [2]}).to_csv(device_map, index=False)

    config = SalesCleaningConfig(
        workbook_path=workbook,
        country_mapping_path=country_map,
        device_to_bay_path=device_map,
    )

    cleaned = run_sales_cleaning_pipeline(config)

    assert len(cleaned) == 4
    assert set(cleaned["source_sheet"]) == {"2021 Sales", "2022 SaaS"}
    assert "Type" in cleaned.columns
    assert "sub_cat" in cleaned.columns
    assert "usd_adjusted_total" in cleaned.columns
    assert cleaned.loc[cleaned["Product"] == "DS220j", "total_bays"].iloc[0] == 16
