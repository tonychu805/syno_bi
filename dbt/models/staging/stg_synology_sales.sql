{#-
  Normalize sale-out history supplied by the ingestion step.
  Update the column mappings to reflect the actual headers present in the workbook.
-#}

{% set sales_sources = var(
    "synosales_sources",
    [
        ("synology_ingestion", "2023_c2", "2023-C2"),
        ("synology_ingestion", "2023", "2023"),
        ("synology_ingestion", "2024_c2", "2024-C2"),
        ("synology_ingestion", "2024", "2024"),
    ],
)%}

with combined as (
    {% for source_schema, table_name, sheet_name in sales_sources %}
    select
        cast("date" as date) as sale_date,
        cast("sku" as text) as sku,
        '{{ sheet_name }}'::text as source_sheet,
        cast("quantity" as numeric) as quantity,
        cast("revenue" as numeric) as revenue
    from {{ source(source_schema, table_name) }}
    {% if not loop.last %}
    union all
    {% endif %}
    {% endfor %}
)

select
    sale_date,
    sku,
    source_sheet as channel,
    quantity,
    revenue
from combined
where sale_date is not null
  and sku is not null
