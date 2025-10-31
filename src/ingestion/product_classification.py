"""Product classification utilities for Synology sales data.

The historical notebooks in ``data/archive`` contain a sizeable amount of
business logic for turning SKU strings into higher-level categories and
sub-categories.  This module ports the pieces that are required for the
modern ingestion pipeline while removing interactive notebook helpers.
"""

from __future__ import annotations

import pandas as pd

_DRIVE_PREFIXES = ("HAT", "HAS", "SNV", "SAT5")
_SERVER_PREFIXES = ("DS", "DX", "RS", "RX", "SA", "HD", "FS", "FX", "UC")
_ACCESSORY_PREFIXES = ("D4", "E10", "E25", "RAM", "M2D", "RKS", "RKM", "BST", "QLE")
_SURVEILLANCE_PREFIXES = ("NVR", "DVA", "VS", "BC", "TC", "CC")
_DLG_PREFIXES = ("BDS", "WRX", "RT", "MR")

_LICENSE_KEYWORDS = (
    "VMM",
    "MAILPLUS",
    "PRESTO",
    "DSM",
    "ACTIVE_INSIGHT",
    "ACTIVE-INSIGHT",
    "SOS",
)

_C2_SAAS_KEYWORDS = (
    "OBJECT",
    "IDENTITY",
    "BACKUP",
    "TRANSFER",
    "PASSWORD",
    "STORAGE_BUSINESS",
    "STORAGE_PERSONAL",
)

_SERVER_OTHER_PRODUCTS = {
    "m2d20 adapter card",
    "e10g22-t1-mini",
    "rks-02",
    "e10m20-t1",
    "e25g21-f2",
    "e10g18-t1",
    "e10g21-f2",
    "ew202",
    "ewplus-2y-online",
    "rkm114",
    "e10g18-t2",
    "m2d18 adapter card",
    "rks-01",
    "adapter 65w_2",
    "ew201 virtual",
    "ew202 virtual",
    "adapter 100w_2",
    "adapter 120w_1",
    "adapter 60w_1",
    "adapter 90w_1",
    "60w adapter level vi_ea10681n-120",
    "adapter 42w_1_au",
    "60w adapter level vi_kpl-060f-vi",
    "ew201",
    "adapter 36w set",
    "rks-03",
    "adapter 30w set",
    "adapter 24w set",
    "adapter 48w/50w_1",
    "adapter 42w_1_uk",
    "rks-02 carton box",
    "rks-02 epe holder set",
    "e10m20-t1 pcba",
    "m2d20 adapter card pcba",
    "e10g22-t1-mini pcba",
    "adapter 24w_1_us",
    "adapter usb3.2 type-c to type-a",
    "e10g18-t1 rubber pad",
    "partition adapter beedrive bds70 v1.0",
    "e10g18-t2 card low profile bkt",
    "e10g18-t2 card standard bkt",
    "e10g18-t1/ e10m20-t1 card standard bkt",
    "adapter 42w_1_eu",
    "e25g30-f2",
    "adapter 42w set",
    "e10g30-t2",
    "adapter 100w",
    "accessory box adapter 100w_2 / 120w_1 v1.0",
    "accessory box adapter 65w_2 v1.0",
    "bst150-4t",
    "qle2692",
    "active insight premium early bird",
    "active insight premium",
}


def _normalise_product_name(product_name: str | float | None) -> str | None:
    """Return the product name normalised for matching or ``None``."""
    if not isinstance(product_name, str):
        return None
    normalized = product_name.strip()
    return normalized or None


def categorize_product(product_name: str | float | None) -> str:
    """Assign a top-level product family using SKU prefixes."""

    normalized = _normalise_product_name(product_name)
    if normalized is None:
        return "Other"

    upper_name = normalized.upper()

    if upper_name.startswith(_DRIVE_PREFIXES):
        return "DRIVE"

    if upper_name.startswith(_SERVER_PREFIXES):
        if " " in upper_name or "_" in upper_name:
            return "Other"
        return "SERVER"

    if upper_name.startswith(_ACCESSORY_PREFIXES) or "ADAPTER" in upper_name:
        return "SVR-ACC"

    if upper_name.startswith("EW") or "EXTENDED WARRANTY" in upper_name:
        return "SVR-EXW"

    if upper_name.startswith(_SURVEILLANCE_PREFIXES) or any(
        keyword in upper_name
        for keyword in (
            "SURVEILLANCE",
            "DEVICE LICENSE",
            "SURVEILLANCE_BASIC",
            "SURVEILLANCE_ADVANCED",
            "SURVEILLANCE_PROFESSIONAL",
        )
    ):
        return "SURVEILLANCE"

    if upper_name.startswith(_DLG_PREFIXES):
        return "DLG"

    if any(keyword in upper_name for keyword in _LICENSE_KEYWORDS):
        return "DSMLICENSE"

    if upper_name.startswith("C2") and any(
        keyword in upper_name for keyword in _C2_SAAS_KEYWORDS
    ):
        return "C2-SAAS"

    if "INSIGHT" in upper_name or (
        upper_name.startswith("C2") and "STORAGE" in upper_name
    ):
        return "C2-HYBRID"

    return "Other"


def categorize_server_subtype(
    product_name: str | float | None, main_category: str
) -> str:
    """Assign a sub-category for server and surveillance SKUs."""

    normalized = _normalise_product_name(product_name)
    if normalized is None:
        return ""

    lower_name = normalized.lower()

    if lower_name in _SERVER_OTHER_PRODUCTS:
        return "Other"

    if main_category == "DRIVE":
        if lower_name.startswith("has"):
            return "DRV-HD-T3"
        if lower_name.startswith("hat53"):
            return "DRV-HD-T2"
        if lower_name.startswith("hat"):
            return "DRV-HD-T1"
        if lower_name.startswith("sat"):
            return "DRV-SD-T2"
        if lower_name.startswith("snv"):
            return "DRV-SD-T1"

    if main_category == "SERVER":
        if lower_name.startswith("ds"):
            if any(term in lower_name for term in ("xs", "xs+", "fs1018", "ds24")):
                return "SVR-DT-DS-T3"
            if "+" in lower_name or "ds620slim" in lower_name:
                return "SVR-DT-DS-T2"
            return "SVR-DT-DS-T1"

        if lower_name.startswith("dx12"):
            return "SVR-DT-DX-T3"
        if lower_name.startswith("dx5"):
            return "SVR-DT-DX-T2"

        if lower_name.startswith(("sa", "hd")) and any(
            term in lower_name for term in ("6400", "6500")
        ):
            return "SVR-RM-GP-T5"
        if lower_name.startswith(("sa", "uc")):
            return "SVR-RM-GP-T4"

        if lower_name.startswith("rs"):
            if "xs+" in lower_name:
                return "SVR-RM-GP-T3"
            if any(term in lower_name for term in ("xs", "rpxs", "rs28", "rs24")):
                return "SVR-RM-GP-T2"
            return "SVR-RM-GP-T1"

        if "rx60" in lower_name:
            return "SVR-RM-GX-T5"
        if lower_name.startswith("rxd") or (
            lower_name.startswith("rx") and "sas" in lower_name
        ):
            return "SVR-RM-GX-T4"
        if lower_name.startswith("rx12") and "rp" in lower_name:
            return "SVR-RM-GX-T3"
        if lower_name.startswith("rx"):
            return "SVR-RM-GX-T2"

        if lower_name.startswith("fs"):
            if "6400" in lower_name:
                return "SVR-RM-FS-T3"
            if any(term in lower_name for term in ("34", "36")):
                return "SVR-RM-FS-T2"
            return "SVR-RM-FS-T1"

        if lower_name.startswith("fx"):
            return "SVR-RM-FX-T2"

    if main_category == "SURVEILLANCE":
        if lower_name.startswith("dva"):
            return "SVS-DT-DVA"
        if lower_name.startswith("nvr"):
            return "SVS-DT-OT"
        if lower_name.startswith("vs"):
            return "SVS-DT-VS"
        if lower_name.startswith(("bc", "tc")):
            return "SVS-CAM"
        if "device license" in lower_name:
            if "8" in lower_name:
                return "SVS-Lx8"
            if "4" in lower_name:
                return "SVS-Lx4"
            if "1" in lower_name:
                return "SVS-Lx1"
        if "surveillance" in lower_name:
            if "basic" in lower_name:
                return "SVS-C2-T1"
            return "SVS-C2-T2"

    if main_category == "DLG":
        if lower_name.startswith(("rt66", "wrx")):
            return "RT-AX"
        if lower_name.startswith(("rt26", "mr", "rt19")):
            return "RT-AC"
        return "BE-D"

    if main_category in {"DSMLICENSE", "Other"}:
        return main_category

    if lower_name.startswith(("d4", "ram", "ddr")):
        return "Memory"

    if main_category in {"C2-SAAS", "C2-HYBRID"}:
        upper_name = normalized.upper()

        if "C2" not in upper_name:
            return ""

        product_type = "UNKNOWN"
        capacity = "UNKNOWN"
        plan = "UNKNOWN"

        if "STORAGE" in upper_name:
            product_type = "STORAGE"
        elif "BACKUP" in upper_name:
            product_type = "BACKUP"
        elif "IDENTITY" in upper_name:
            product_type = "IDENTITY"
        elif "OBJECT" in upper_name:
            product_type = "OBJECT"
        elif "PASSWORD" in upper_name:
            product_type = "PASSWORD"
        elif "TRANSFER" in upper_name:
            product_type = "TRANSFER"

        if "1T" in upper_name:
            capacity = "1T"
        elif "100G" in upper_name:
            capacity = "100G"
        elif "500G" in upper_name:
            capacity = "500G"
        elif "2T" in upper_name:
            capacity = "2T"
        elif "5T" in upper_name:
            capacity = "5T"

        if "BASIC" in upper_name:
            plan = "BASIC"
        elif "INDIVIDUAL" in upper_name:
            plan = "INDIVIDUAL"
        elif "BUSINESS" in upper_name:
            plan = "BUSINESS"
        elif "ADV" in upper_name or "ADVANCED" in upper_name:
            plan = "ADVANCED"
        elif "ENTERPRISE" in upper_name:
            plan = "ENTERPRISE"
        elif "PROFESSIONAL" in upper_name:
            plan = "PROFESSIONAL"

        return f"C2-{product_type}-{capacity}-{plan}"

    return ""


def assign_product_category(
    frame: pd.DataFrame, product_column: str = "Product"
) -> pd.Series:
    """Vectorised wrapper for :func:`categorize_product`."""

    return frame[product_column].apply(categorize_product)


def assign_product_subcategory(
    frame: pd.DataFrame,
    *,
    product_column: str = "Product",
    category_column: str = "Type",
) -> pd.Series:
    """Vectorised wrapper for :func:`categorize_server_subtype`."""

    return frame.apply(
        lambda row: categorize_server_subtype(
            row[product_column], row[category_column]
        ),
        axis=1,
    )


def extract_drive_capacities(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a lookup table of drive capacities in gigabytes."""

    drives = frame[frame["Type"] == "DRIVE"]["Product"].dropna().astype(str).unique()
    drive_frame = pd.DataFrame({"Product": drives})

    capacity_frame = drive_frame[
        drive_frame["Product"].str.match(
            r"^[A-Z0-9]+-[0-9]+[GT](\s*\(.*\))?$", na=False
        )
    ].copy()

    capacity_frame.loc[:, "Capacity"] = capacity_frame["Product"].str.split("-").str[1]
    capacity_frame.loc[:, "Capacity"] = capacity_frame["Capacity"].str.extract(
        r"(\d+)"
    )[0]
    capacity_frame.loc[:, "Capacity"] = (
        capacity_frame["Capacity"].str.replace("G", "").str.replace("T", "").astype(int)
    )

    capacity_frame.loc[:, "Capacity"] = capacity_frame.apply(
        lambda row: (
            row["Capacity"] * 1000 if row["Product"].endswith("T") else row["Capacity"]
        ),
        axis=1,
    )
    capacity_frame.loc[:, "Unit"] = "GB"
    return capacity_frame


def attach_drive_capacity(frame: pd.DataFrame) -> pd.DataFrame:
    """Augment ``frame`` with drive capacity columns."""

    capacity_frame = extract_drive_capacities(frame)
    merged = frame.merge(capacity_frame, on="Product", how="left")
    quantity = merged["Quantity"].where(merged["Type"] == "DRIVE", 0).fillna(0)
    capacity = merged["Capacity"].fillna(0)
    merged["total_cap"] = quantity * capacity
    return merged


def assign_product_categories(
    frame: pd.DataFrame,
    *,
    product_column: str = "Product",
    type_column: str = "Type",
    subtype_column: str = "sub_cat",
) -> pd.DataFrame:
    """Mutate ``frame`` with type and sub-type classification."""

    frame = frame.copy()
    frame[type_column] = assign_product_category(frame, product_column)
    frame[subtype_column] = assign_product_subcategory(
        frame, product_column=product_column, category_column=type_column
    )
    return frame
