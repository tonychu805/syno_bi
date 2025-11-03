import pandas as pd
from pandas.testing import assert_frame_equal

from src.forecasting.preprocessing import (
    prepare_quarterly_dataset,
    prepare_quarterly_views,
    split_latest_quarter,
    tag_focus_products,
)


def test_prepare_quarterly_dataset_aggregates_and_fills_quarters() -> None:
    data = pd.DataFrame(
        {
            "invoice_date": pd.to_datetime(
                [
                    "2023-01-15",
                    "2023-02-10",
                    "2023-04-05",
                    "2023-01-07",
                    "2023-03-19",
                    "2023-06-02",
                ]
            ),
            "usd_adjusted_total": [100.0, 50.0, 200.0, 80.0, 120.0, 150.0],
            "Type": ["Cloud", "Cloud", "Cloud", "Hardware", "Hardware", "Hardware"],
        }
    )

    result = prepare_quarterly_dataset(
        data,
        value_column="usd_adjusted_total",
        segment_columns=("Type",),
        date_candidates=("invoice_date",),
    )

    expected = pd.DataFrame(
        {
            "Type": ["Cloud", "Cloud", "Hardware", "Hardware"],
            "sale_quarter": pd.PeriodIndex(["2023Q1", "2023Q2", "2023Q1", "2023Q2"], freq="Q"),
            "quarter_total": [150.0, 200.0, 200.0, 150.0],
            "quarter_start": pd.to_datetime(
                ["2023-01-01", "2023-04-01", "2023-01-01", "2023-04-01"]
            ),
            "quarter_end": pd.to_datetime(
                ["2023-03-31", "2023-06-30", "2023-03-31", "2023-06-30"]
            ),
        }
    )

    assert_frame_equal(result.reset_index(drop=True), expected)


def test_split_latest_quarter_returns_expected_partitions() -> None:
    aggregated = pd.DataFrame(
        {
            "Type": ["Cloud", "Cloud", "Hardware", "Hardware"],
            "sale_quarter": pd.PeriodIndex(["2023Q1", "2023Q2", "2023Q1", "2023Q2"], freq="Q"),
            "quarter_total": [150.0, 200.0, 200.0, 150.0],
        }
    )

    train, test, latest = split_latest_quarter(aggregated)

    assert latest == pd.Period("2023Q2", freq="Q")
    assert all(train["sale_quarter"] == pd.Period("2023Q1", freq="Q"))
    assert all(test["sale_quarter"] == pd.Period("2023Q2", freq="Q"))


def test_prepare_quarterly_dataset_raises_when_missing_date_column() -> None:
    data = pd.DataFrame({"usd_adjusted_total": [10, 20, 30]})

    try:
        prepare_quarterly_dataset(data)
    except ValueError as exc:
        assert "No supported date column" in str(exc)
    else:
        raise AssertionError("Expected ValueError when no date columns are present.")


def test_tag_focus_products_marks_expected_rows() -> None:
    df = pd.DataFrame(
        {
            "Product": ["SVR-DT-DS-T1", "NAS-OTHER"],
            "usd_adjusted_total": [100.0, 50.0],
        }
    )

    tagged = tag_focus_products(df, focus_products=("SVR-DT-DS-T1",))
    assert tagged["is_focus_product"].tolist() == [True, False]


def test_prepare_quarterly_views_returns_global_and_focus() -> None:
    df = pd.DataFrame(
        {
            "invoice_date": pd.to_datetime(["2023-01-15", "2023-02-10", "2023-05-01"]),
            "usd_adjusted_total": [100.0, 80.0, 120.0],
            "Product": ["SVR-DT-DS-T1", "NAS-OTHER", "SVR-DT-DS-T1"],
            "Type": ["Cloud", "Cloud", "Cloud"],
        }
    )

    global_df, focus_df = prepare_quarterly_views(
        df,
        value_column="usd_adjusted_total",
        segment_columns=("Product", "Type"),
        date_candidates=("invoice_date",),
        focus_products=("SVR-DT-DS-T1",),
    )

    assert set(global_df["Product"]) == {"SVR-DT-DS-T1", "NAS-OTHER"}
    assert set(global_df["is_focus_product"]) == {True, False}
    assert set(focus_df["Product"]) == {"SVR-DT-DS-T1"}
    assert set(focus_df["is_focus_product"]) == {True}
