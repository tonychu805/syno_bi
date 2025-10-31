from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.ingestion import SalesCleaningConfig, run_sales_cleaning_pipeline


def test_pipeline_combines_and_enriches_workbook(tmp_path: Path) -> None:
    raw = pd.DataFrame(
        {
            "Product": ["DS220j", "HAT5300-8T", "C2 Storage Advanced", "Adapter 65W_2"],
            "Currency": ["USD", "USD", "EUR", "EUR"],
            "Price": [132.0, 200.0, 18.2, 25.0],
            "Total": [1056.0, 800.0, 18.2, 25.0],
            "Quantity": [8, 4, 1, 2],
            "InvDate": ["2021-01-04", "2021-05-06", "2022-02-01", "2022-02-02"],
            "Country": ["United States", "United States", "Germany", "Germany"],
            "source_sheet": ["2021 Sales", "2021 Sales", "2022 SaaS", "2022 SaaS"],
        }
    )

    country_map = tmp_path / "countries.csv"
    pd.DataFrame(
        {"Country": ["United States", "Germany"], "Region": ["NA", "DE"]}
    ).to_csv(country_map, index=False)

    device_map = tmp_path / "device_bays.csv"
    pd.DataFrame({"Product": ["DS220j"], "Bays": [2]}).to_csv(device_map, index=False)

    config = SalesCleaningConfig(
        workbook_path=tmp_path / "synology.xlsx",
        country_mapping_path=country_map,
        device_to_bay_path=device_map,
    )

    with patch("src.ingestion.sales_cleaning._load_workbook", return_value=raw):
        cleaned = run_sales_cleaning_pipeline(config)

    assert len(cleaned) == 4
    assert set(cleaned["source_sheet"]) == {"2021 Sales", "2022 SaaS"}
    assert "Type" in cleaned.columns
    assert "sub_cat" in cleaned.columns
    assert "usd_adjusted_total" in cleaned.columns
    assert cleaned.loc[cleaned["Product"] == "DS220j", "total_bays"].iloc[0] == 16
