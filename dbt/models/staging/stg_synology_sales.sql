{#-
  Normalize sale-out history supplied by the ingestion step.
  Update the column mappings to reflect the actual headers present in the workbook.
-#}

{% set sales_sources = [
    ("synology_ingestion", "im_sales_history_2023", "IM"),
    ("synology_ingestion", "im_sales_history_2024", "IM"),
    ("synology_ingestion", "im_sales_history_2025", "IM"),
    ("synology_ingestion", "tdbs_sales_history_2023", "TDBS"),
    ("synology_ingestion", "tdbs_sales_history_2024", "TDBS"),
] %}

with combined as (
    {% for source_schema, table_name, channel in sales_sources %}
    select
        cast("date" as date) as sale_date,
        cast("sku" as text) as sku,
        '{{ channel }}'::text as channel,
        cast("quantity" as numeric) as quantity,
        cast("revenue" as numeric) as revenue
    from {{ source(source_schema, table_name) }}
    {% if not loop.last %}
    union all
    {% endif %}
    {% endfor %}
)

select *
from combined
where sale_date is not null
  and sku is not null;
