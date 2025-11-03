# Sales Staging Data Dictionary (November 2025)

## Purpose
Document the curated column set produced by the `stg_synology_sales` model so forecasting, BI, and QA teams understand which fields survive the staging step and why. This sheet complements the retention policy outlined in `phases/02_preprocessing.md` and should be refreshed whenever new Synology workbook tabs or columns are added.

## Column Disposition

| Column Group | Keep / Drop | Rationale | Notes |
| --- | --- | --- | --- |
| `Customer`, `Product`, `Type`, `sub_cat` | **Keep** | Defines commercial grain for SVR-RM and consumer trend marts. | Preserve raw casing; normalize in marts if needed. |
| Geographic attributes (`Country`, mapped `Region`, `Subregion`) | **Keep** | Required for regional and channel segmentation. | Region mappings stored in mapping_table seeds. |
| `Quantity` | **Keep** | Core volume metric; feeds baseline regression + SVR models. | Cast to numeric after blank/NULL guard. |
| `usd_adjusted_total`, `usd_adjusted_price`, `exchange_rate_to_usd` | **Keep** | Enables multi-currency comparability and QA back-calculation. | `exchange_rate_to_usd` can migrate to lookup later if auditors approve. |
| `total_cap` | **Keep** | Used in DS trend forecasting to model storage capacity purchased. | Derived in downstream mart; staging ensures base inputs exist. |
| Derived temporal fields (`sale_date`, `sale_quarter`, `sale_month`) | **Keep** | Drives seasonality features and KPI rollups. | `sale_date` sourced from `InvDate` with safe casting. |
| `PI`, `InvDate`, `ShipDate` | Drop after derivation | Invoice identifiers clutter joins; `InvDate` only retained long enough to populate `sale_date`. | Archive raw fields in QA log if auditors require traceability. |
| `ItemCode`, `DeliveryFrom`, `ShipTo` | Drop (conditional) | Low coverage (~85%); optional for SKU-to-ERP reconciliation. | Retain only when reconciliation KPIs are in scope. |
| `Comments` | Drop | Sparse free text (≤3% populated). | Consider separate QA/NLP pipeline if needed. |
| `Currency`, `Price`, `Total` | Drop | Redundant once USD-adjusted measures materialise; avoid double counting. | Keep one set of measures to simplify audits. |
| Discount fields (`T/T Discount`, `Discount`) | Drop | Mostly zeros; fold adjustment into revenue before aggregation. | Document discount treatment in quality gates if strategy changes. |
| `source_sheet` | Drop from marts | Helpful for debugging but not a business dimension. | Persist in profiling log only. |

## Casting & Cleaning Rules
- Trim whitespace and treat `''`, `'NULL'`, and `'null'` as missing before casting.
- Validate `InvDate` format (`YYYY-MM-DD`); fallback to `ShipDate` only when explicit business logic requires it.
- Numeric fields (`Quantity`, `Total`, discounts) cast to `numeric` only when the trimmed string matches a decimal pattern; otherwise set to `NULL`.

## QA Checklist
1. dbt run: `dbt run --select stg_synology_sales` (after seed refresh).
2. dbt tests: ensure `sale_date` and `sku` remain `not_null`.
3. Notebook QA cell: confirm quarterly aggregates and regional splits match historical baselines after column drops.
4. Update this dictionary and `phases/02_preprocessing.md` if any new columns are introduced or retention decisions change.
