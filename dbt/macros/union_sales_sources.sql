{% macro union_sales_sources(sources_list) %}
{% if sources_list | length == 0 %}
select
    null::date as sale_date,
    null::text as item_code,
    null::text as product_name,
    null::text as sku,
    null::text as channel,
    null::numeric as quantity,
    null::numeric as revenue
where 1 = 0
{% else %}
with combined as (
    {% for source_schema, table_name, sheet_name in sources_list %}
    select
        case
            when regexp_match(trim("InvDate"::text), '^\d{4}-\d{2}-\d{2}$') is not null
                then trim("InvDate"::text)::date
            else null
        end as sale_date,
        cast(nullif(trim("ItemCode"::text), '') as text) as item_code,
        cast(nullif(trim("Product"::text), '') as text) as product_name,
        cast(
            coalesce(
                nullif(trim("ItemCode"::text), ''),
                nullif(trim("Product"::text), '')
            ) as text
        ) as sku,
        '{{ sheet_name }}'::text as channel,
        case
            when regexp_match(trim("Quantity"::text), '^-?\d+(?:\.\d+)?$') is not null
                then greatest(trim("Quantity"::text)::numeric, 0)
            else null
        end as quantity,
        case
            when regexp_match(trim("Total"::text), '^-?\d+(?:\.\d+)?$') is not null
                then greatest(trim("Total"::text)::numeric, 0)
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
    item_code,
    product_name,
    sku,
    channel,
    quantity,
    revenue
from combined
where sale_date is not null
  and sku is not null
{% endif %}
{% endmacro %}
