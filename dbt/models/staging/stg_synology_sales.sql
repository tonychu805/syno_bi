{#-
  Normalize sale-out history supplied by the ingestion step.
  Update the column mappings to reflect the actual headers present in the workbook.
-#}

{% set sales_sources = var(
    "synosales_sources",
    [
        ("synology_ingestion", "2023_c2", "2023-C2"),
        ("synology_ingestion", "seed_sales_2023", "2023"),
        ("synology_ingestion", "2024_c2", "2024-C2"),
        ("synology_ingestion", "seed_sales_2024", "2024"),
    ],
)%}

{% set suite_a_sources = var(
    "synosales_suite_a_sources",
    [
        ("synology_ingestion", "seed_sales_2023", "2023"),
        ("synology_ingestion", "seed_sales_2024", "2024"),
    ]
)%}

{% set suite_b_sources = var(
    "synosales_suite_b_sources",
    [
        ("synology_ingestion", "2023_c2", "2023-C2"),
        ("synology_ingestion", "2024_c2", "2024-C2"),
    ]
)%}

{{
    config(
        materialized='table',
        post_hook=[
            "create or replace view {{ model.schema }}.stg_synology_sales_suite_a as ({{ union_sales_sources(suite_a_sources) }})",
            "create or replace view {{ model.schema }}.stg_synology_sales_suite_b as ({{ union_sales_sources(suite_b_sources) }})"
        ]
    )
}}

{{ union_sales_sources(sales_sources) }}
