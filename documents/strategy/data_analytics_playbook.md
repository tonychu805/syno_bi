# Data Analytics Playbook

This guide walks through the analytics workflow expected for the Synology BI platform. Use it as a checklist when tackling new analyses or maintaining existing ones.

---

## 1. Understand the Business Question

- Clarify objectives with stakeholders (sales, marketing, leadership).  
- Identify **target metrics** (e.g., sell-through, revenue growth, conversion rate).  
- Determine **granularity** (daily/monthly, SKU/channel/region).  
- Document assumptions in the analysis brief before touching data.

### Key questions to ask
1. What decision will this analysis influence?  
2. Which time frame and geographies matter?  
3. Are there known data caveats (missing regions, delayed reporting)?

---

## 2. Gather Data in the Warehouse

- Use dbt staging and mart tables as primary sources (`syno_bi.analytics`).  
- Query via pgAdmin, Metabase SQL editor, or Python notebooks (inside `dbt-runner` container).  
- Avoid working directly on `raw/` files unless the staging layer is incomplete.

### Example warehouse query
```sql
SELECT
  sale_date,
  sku,
  channel,
  quantity,
  revenue
FROM analytics.fact_channel_sales
WHERE sale_date BETWEEN '2024-01-01' AND '2024-06-30';
```

---

## 3. Exploratory Data Analysis (EDA)

### Tools
- Python notebooks (`notebook/sandbox.ipynb`) using pandas/seaborn.  
- Metabase ad-hoc questions.  
- SQL queries in pgAdmin.

### Checklist
- **Data shape**: row counts, unique SKUs/channels.  
- **Distribution**: histograms, box plots for quantity/revenue.  
- **Missing data**: identify nulls and unexpected zeros.  
- **Seasonality**: line charts across months/quarters.  
- **Anomalies**: sudden spikes, drops, outliers.

### Sample Python EDA
```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://analytics:***@postgres:5432/syno_bi")

df = pd.read_sql("SELECT sale_date, sku, channel, quantity, revenue FROM analytics.fact_channel_sales", engine)
df.describe()
```

Record findings, especially data quality issues, in analysis notes or `documents/data_quality_log.md`.

---

## 4. Data Cleaning & Feature Engineering

- Implement corrections in dbt models when possible so improvements are reusable, especially for SVR-RM T1/T2/T3, top-customer revenue slices, Synology C2 adoption metrics, and commercial activation storytelling fields.  
- For ad-hoc analysis, use pandas transformations but plan to push them upstream if they become standard.  
- Track changes in dbt YAML docs (column descriptions, tests) and confirm cleaned tables retain a ready-to-aggregate quarterly grain that supports the next-quarter sales forecast objective.

### Common cleaning steps
1. Standardize SKU/channel names (`UPPER`, trimming).  
2. Handling nulls (`COALESCE`, fill methods).  
3. Creating time features (month bucket, quarter, fiscal year).  
4. Aggregating metrics (rolling averages, cumulative sums).

### Feature engineering example (dbt)
```sql
select
  sale_date,
  sku,
  channel,
  quantity,
  revenue,
  avg(quantity) over (partition by sku, channel order by sale_date rows between 2 preceding and current row) as qty_ma3
from {{ ref('stg_synology_sales') }}
```

Add a matching test + description to the YAML file.

---

## 5. Target Selection & Segmentation

- Define the population of interest (e.g., SVR-RM T1/T2/T3 cohorts, top 5 customers by revenue, Synology C2 service tiers, commercial activation segments).  
- Use dbt exposures or Metabase segments to save frequently used filters.  
- Validate target lists with business stakeholders before running forecasts or campaigns.

### Example target query
```sql
SELECT sku
FROM analytics.dim_sku
WHERE product_line = 'NAS'
  AND lifecycle_stage = 'Growth'
  AND region IN ('US', 'EU', 'APAC');
```

---

## 6. Statistical Modelling / Forecasting

- Start with baseline models (`src/forecasting/regression.py` uses rolling means) that deliver a next-quarter forecast aligned with the accuracy benchmarks agreed with stakeholders for SVR-RM T1/T2/T3 (overall + top customers) and Synology C2 exploratory signals.  
- Treat Synology C2 adoption trends as analytic outputs (growth, retention, upsell signals) and integrate them with forecast storytelling.  
- Evaluate metrics (MAPE, sMAPE, WAPE).  
- Document experiments in `documents/model_eval.md` (input features, hyperparameters, performance).  
- Promote successful models by updating the forecasting module and scheduling in Airflow.
- Ensure Metabase-facing marts continue to expose the full product catalog; provide clear filters or segments identifying the SVR subset used in modeling.

### Guidance
- Maintain train/test splits (e.g., last 3 months as holdout).  
- Use `sklearn`, `statsmodels`, or `prophet` inside the Python container when exploring alternatives.  
- Persist model artifacts/metrics in `data/processed/forecasts/` for versioning.

---

## 7. Insight Generation & Storytelling

- Translate statistical findings into plain language: “Channel IM growing +12% QoQ driven by SKU X”.  
- Provide context: compare to target, historical performance, or market benchmarks.  
- Highlight risks/limitations (data gaps, assumptions).

### Deliverables
- Metabase dashboards (add cards to collections with descriptions).  
- Written summaries (`documents/reports/`).  
- Executive slides referencing key charts, with appendix for methodology.

---

## 8. Operationalising Results

- Update Airflow schedules to automate refresh cadence.  
- Set alerts (`PIPELINE_ALERT_RECIPIENTS`) for anomalies/failures.  
- Create Metabase subscriptions for stakeholders.  
- Log changes in `documents/changelog.md` (new models, dashboards, data fixes).

---

## 9. Tools & Access Summary

| Phase | Primary Tools | Languages |
| --- | --- | --- |
| Ingestion | Python scripts, Airflow | Python |
| EDA | Jupyter notebooks, Metabase, SQL | Python, SQL |
| Cleaning/Modeling | dbt, pandas, SQL | SQL, Python |
| Forecasting | Python modules, Airflow tasks | Python |
| Visualization | Metabase, pgAdmin (for SQL) | SQL |
| Documentation | Markdown in `documents/`, dbt docs | Markdown, YAML |

---

## 10. Best Practices for Junior Analysts

1. **Version Control:** commit code/model changes with descriptive messages; avoid editing `main` directly.  
2. **Reproducibility:** keep notebooks deterministic; record random seeds and environment details.  
3. **Data Integrity:** always run `dbt test` after modifying models; never overwrite `raw/`.  
4. **Communication:** summarise findings with business implications; tag pending questions in reports.  
5. **Security:** treat credentials in `env/` as secrets; request access through project lead when needed.  
6. **Continuous learning:** review dbt docs at `http://<NAS-IP>:8081` and Metabase dashboards to understand existing transformations.

---

Use this playbook alongside the technical reference (`documents/data_pipeline_reference.md`) to deliver analyses consistently and effectively. Update the playbook when new workflows or standards are introduced. 
