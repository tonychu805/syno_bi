# Objective 2 – Synology C2 Adoption Dashboard Queries

This note captures the SQL canon for Objective 2 (“Synology C2 Exploratory Analysis”). Each query runs directly against `analytics.c2_adoption_scorecard`, the table populated by the `syno_c2_adoption` Airflow DAG after the transform pipeline finishes.

## Dataset Reference

| Column | Description |
| --- | --- |
| `snapshot_month` | Month-end date for the adoption snapshot |
| `service_family` | Parsed from `sub_cat` (e.g., STORAGE, BACKUP) |
| `plan_variant` | Parsed plan/offer variant |
| `region` | Sales region derived in preprocessing |
| `customer_tier` | Tier label (Top 5, Top 20, Long Tail) based on revenue concentration |
| `sku` | Currently set to `ALL` (placeholder for future SKU split) |
| `active_subscriptions` | Distinct customers active in the month |
| `new_subscriptions` | Distinct PI/order IDs in the month |
| `mrr_usd` | Monthly recurring revenue proxy (USD) aggregated from invoice totals |
| `total_quantity` | Total unit quantity shipped |
| `avg_seats` | Seat proxy = quantity ÷ active subs |
| `created_at` | Load timestamp |

> Adjust the literal dates/service families below to match your reporting window. The SQL structures stay the same if you later parameterize them inside Metabase or dbt exposures.

---

## 1. Adoption Snapshot Tiles

Description: Summarizes the latest Storage snapshot across 2023-2024 to populate the executive KPI tiles outlined in `documents/implementation/summary.md`, blending base (active), velocity (new), MRR, quantity, and weighted seat mix for a single-glance health check.
Visualization: Multi-metric KPI tile row (single-value cards or scorecards).

```sql
WITH latest AS (
    SELECT MAX(snapshot_month) AS latest_snapshot
    FROM analytics.c2_adoption_scorecard
    WHERE service_family = 'STORAGE'
      AND snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
)
SELECT
    l.latest_snapshot,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(mrr_usd) AS mrr_usd,
    SUM(total_quantity) AS total_quantity,
    SUM(active_subscriptions * avg_seats)
        / NULLIF(SUM(active_subscriptions), 0) AS weighted_avg_seats
FROM analytics.c2_adoption_scorecard AS s
CROSS JOIN latest AS l
WHERE s.snapshot_month = l.latest_snapshot
  AND s.service_family = 'STORAGE';
```

---

## 2. Regional MRR Heatmap

Description: Produces a month-region-service matrix of MRR and new subscriptions that powers the geographic heatmap recommended in `documents/strategy/data_analytics_playbook.md`, highlighting where to double down or intervene on coverage.
Visualization: Time-series heatmap (snapshot_month on X, region on Y, color = MRR) or stacked area by region.

```sql
SELECT
    snapshot_month,
    region,
    service_family,
    SUM(mrr_usd) AS mrr_usd,
    SUM(new_subscriptions) AS new_subscriptions
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, region, service_family
ORDER BY snapshot_month, region, service_family;
```

---

## 3. Customer Tier Contribution

Description: Breaks adoption performance into the Top 5, Top 20, and long-tail tiers so we can evidence concentration risk and account focus decisions referenced in `documents/strategy/PRD.md`.
Visualization: Stacked column/area chart with snapshot_month on X and tier segments.

```sql
SELECT
    snapshot_month,
    customer_tier,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(mrr_usd) AS mrr_usd,
    SUM(active_subscriptions * avg_seats)
        / NULLIF(SUM(active_subscriptions), 0) AS weighted_avg_seats
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, customer_tier
ORDER BY snapshot_month, customer_tier;
```

---

## 4. Plan Variant Mix (Latest Month)

Description: Compares the latest-month contribution of each plan_variant to show packaging impact, justify roadmap bets, and flag cannibalization in line with the commercialization narrative in the implementation summary.
Visualization: Sorted horizontal bar chart or donut slice for latest-month share.

```sql
SELECT
    plan_variant,
    SUM(mrr_usd) AS mrr_usd,
    SUM(total_quantity) AS total_quantity,
    SUM(new_subscriptions) AS new_subscriptions
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month = DATE '2024-10-31'
GROUP BY plan_variant
ORDER BY mrr_usd DESC;
```

---

## 5. Adoption Trend Lines (Installed Base vs Velocity)

Description: Builds the dual-line chart for APAC Storage that tracks installed base (active) versus velocity (new) so business partners can see whether momentum is keeping pace with the installed base commitments.
Visualization: Dual-axis line chart (active vs new) with optional service_family breakout for multiple series.

```sql
SELECT
    snapshot_month,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(mrr_usd) AS mrr_usd
FROM analytics.c2_adoption_scorecard
WHERE region = 'APAC'
  AND service_family = 'STORAGE'
GROUP BY snapshot_month
ORDER BY snapshot_month;
```

---

## 6. Service Family Growth Table (QoQ Change)

Description: Calculates quarter-over-quarter MRR deltas by service_family, mirroring the growth diagnostics step in `documents/implementation/phases/06_quality_gates.md` so we can call out inflections or regressions.
Visualization: Table with conditional formatting on QoQ change or clustered bar chart of MRR vs prior MRR.

```sql
WITH quarterly AS (
    SELECT
        DATE_TRUNC('quarter', snapshot_month) AS quarter_start,
        service_family,
        SUM(mrr_usd) AS mrr_usd,
        SUM(active_subscriptions) AS active_subscriptions
    FROM analytics.c2_adoption_scorecard
    GROUP BY DATE_TRUNC('quarter', snapshot_month), service_family
),
ranked AS (
    SELECT
        quarter_start,
        service_family,
        mrr_usd,
        LAG(mrr_usd, 1) OVER (PARTITION BY service_family ORDER BY quarter_start) AS prior_mrr_usd,
        active_subscriptions
    FROM quarterly
)
SELECT
    quarter_start AS snapshot_quarter,
    service_family,
    mrr_usd,
    prior_mrr_usd,
    ROUND((mrr_usd - prior_mrr_usd) / NULLIF(prior_mrr_usd, 0) * 100, 2) AS mrr_percentage_change,
    active_subscriptions
FROM ranked
WHERE quarter_start BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
ORDER BY quarter_start DESC, mrr_percentage_change DESC;
```

---

## 7. Regional Drilldown Table

Description: Provides the fully sliceable table (region x tier x family x plan) that CS and finance teams use for drilldowns, enabling ad-hoc pivots without leaving the dashboard.
Visualization: Interactive pivot-style table with sortable columns and filters.

```sql
SELECT
    snapshot_month,
    region,
    customer_tier,
    service_family,
    plan_variant,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(mrr_usd) AS mrr_usd,
    SUM(total_quantity) AS total_quantity,
    SUM(active_subscriptions * avg_seats)
        / NULLIF(SUM(active_subscriptions), 0) AS weighted_avg_seats
FROM analytics.c2_adoption_scorecard
WHERE snapshot_month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31'
GROUP BY snapshot_month, region, customer_tier, service_family, plan_variant
ORDER BY snapshot_month DESC, mrr_usd DESC;
```

---

## 8. Quality / Freshness Check

Description: Runs a quick freshness check before surfacing the dashboard, confirming the latest snapshot date, row volume, subscription totals, and MRR per the guardrails in `documents/implementation/phases/06_quality_gates.md`.
Visualization: Status tile or traffic-light card with latest snapshot date plus row/subscription counters.

```sql
SELECT
    MAX(snapshot_month) AS latest_snapshot,
    COUNT(*) AS row_count,
    SUM(active_subscriptions) AS active_subscriptions,
    SUM(new_subscriptions) AS new_subscriptions,
    SUM(mrr_usd) AS mrr_usd
FROM analytics.c2_adoption_scorecard;
```

---

**Next steps:** plug these SQL blocks into Metabase cards (or dbt exposures), tweak the literal dates/service families as needed, and ensure the Objective 2 dashboard is tied into the `syno_activation` Metabase refresh so it updates automatically after each `syno_c2_adoption` run.
