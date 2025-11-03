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

with combined as (
    {% for source_schema, table_name, sheet_name in sales_sources %}
    select
        case
            when regexp_match(trim("InvDate"::text), '^\d{4}-\d{2}-\d{2}$') is not null
                then trim("InvDate"::text)::date
            else null
        end as sale_date,
        cast(
            coalesce(
                nullif(trim("ItemCode"::text), ''),
                nullif(trim("Product"::text), '')
            ) as text
        ) as sku,
        '{{ sheet_name }}'::text as source_sheet,
        case
            when regexp_match(trim("Quantity"::text), '^-?\d+(?:\.\d+)?$') is not null
                then trim("Quantity"::text)::numeric
            else null
        end as quantity,
        case
            when regexp_match(trim("Total"::text), '^-?\d+(?:\.\d+)?$') is not null
                then trim("Total"::text)::numeric
            else null
        end as revenue
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
