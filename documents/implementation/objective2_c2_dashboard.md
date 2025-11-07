# Objective 2 – Synology C2 Adoption Dashboard Queries

This note captures the SQL canon for Objective 2 (“Synology C2 Exploratory Analysis”). Each query runs directly against `analytics.c2_adoption_scorecard`, the table populated by the `syno_c2_adoption` Airflow DAG after the transform pipeline finishes.

## Dataset Reference

| Column | Description |
| --- | --- |
| `snapshot_month` | Month-end date for the adoption snapshot |
| `service_family` | Parsed from `sub_cat` (e.g., STORAGE, BACKUP) |
| `plan_variant` | Parsed plan/offer variant |
| `region` | Sales region derived in preprocessing |
| `customer_tier` | Tier label (Top 5, Top 20, Long Tail) based on ARR |
| `sku` | Currently set to `ALL` (placeholder for future SKU split) |
| `active_subscriptions` | Distinct customers active in the month |
| `new_subscriptions` | Distinct PI/order IDs in the month |
| `arr_usd` | Aggregated ARR proxy (USD) |
| `total_quantity` | Total unit quantity shipped |
| `avg_seats` | Seat proxy = quantity ÷ active subs |
| `created_at` | Load timestamp |

> Adjust the literal dates/service families below to match your reporting window. The SQL structures stay the same if you later parameterize them inside Metabase or dbt exposures.

---

## 1. Adoption Snapshot Tiles

```sql
SELECT
    MAX(snapshot_month) AS latest_snapshot,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(arr_usd) AS arr_usd,
    SUM(total_quantity) AS total_quantity,
    SUM(active_subscriptions * avg_seats)
        / NULLIF(SUM(active_subscriptions), 0) AS weighted_avg_seats
FROM analytics.c2_adoption_scorecard AS s
WHERE s.snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
  AND s.service_family = 'STORAGE';
```

---

## 2. Regional ARR Heatmap

```sql
SELECT
    snapshot_month,
    region,
    service_family,
    SUM(arr_usd) AS arr_usd,
    SUM(new_subscriptions) AS new_subscriptions
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, region, service_family
ORDER BY snapshot_month, region, service_family;
```

---

## 3. Customer Tier Contribution

```sql
SELECT
    snapshot_month,
    customer_tier,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(arr_usd) AS arr_usd,
    AVG(avg_seats) AS avg_seats
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, customer_tier
ORDER BY snapshot_month, customer_tier;
```

---

## 4. Plan Variant Mix (Latest Month)

```sql
SELECT
    plan_variant,
    SUM(arr_usd) AS arr_usd,
    SUM(total_quantity) AS total_quantity,
    SUM(new_subscriptions) AS new_subscriptions
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month = DATE '2024-10-31'
GROUP BY plan_variant
ORDER BY arr_usd DESC;
```

---

## 5. Adoption Trend Lines (Installed Base vs Velocity)

```sql
SELECT
    snapshot_month,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(arr_usd) AS arr_usd
FROM analytics.c2_adoption_scorecard
WHERE region = 'APAC'
  AND service_family = 'STORAGE'
GROUP BY snapshot_month
ORDER BY snapshot_month;
```

---

## 6. Service Family Growth Table (QoQ Change)

```sql
WITH monthly AS (
    SELECT
        snapshot_month,
        service_family,
        SUM(arr_usd) AS arr_usd,
        SUM(active_subscriptions) AS active_subscriptions
    FROM analytics.c2_adoption_scorecard
    GROUP BY snapshot_month, service_family
),
ranked AS (
    SELECT
        snapshot_month,
        service_family,
        arr_usd,
        LAG(arr_usd, 1) OVER (PARTITION BY service_family ORDER BY snapshot_month) AS prior_arr_usd,
        active_subscriptions
    FROM monthly
)
SELECT
    snapshot_month,
    service_family,
    arr_usd,
    prior_arr_usd,
    arr_usd - prior_arr_usd AS arr_change,
    active_subscriptions
FROM ranked
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
ORDER BY snapshot_month DESC, arr_change DESC;
```

---

## 7. Regional Drilldown Table

```sql
SELECT
    snapshot_month,
    region,
    customer_tier,
    service_family,
    plan_variant,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(arr_usd) AS arr_usd,
    SUM(total_quantity) AS total_quantity,
    AVG(avg_seats) AS avg_seats
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, region, customer_tier, service_family, plan_variant
ORDER BY snapshot_month DESC, arr_usd DESC;
```

---

## 8. Quality / Freshness Check

```sql
SELECT
    MAX(snapshot_month) AS latest_snapshot,
    COUNT(*) AS row_count,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions
FROM analytics.c2_adoption_scorecard;
```

---

**Next steps:** plug these SQL blocks into Metabase cards (or dbt exposures), tweak the literal dates/service families as needed, and ensure the Objective 2 dashboard is tied into the `syno_activation` Metabase refresh so it updates automatically after each `syno_c2_adoption` run.
