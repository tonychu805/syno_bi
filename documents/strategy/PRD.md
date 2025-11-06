# Project Requirement Document (PRD)

## Project Title
Synology Global BI Platform - Sales Forecasting & Market Intelligence Framework

## 1. Project Overview

The Synology Global BI Platform is a strategic initiative designed to unify disparate data sources across regional sales, marketing, and distribution channels into a single analytical ecosystem. It aims to deliver actionable insights through automated dashboards, predictive modeling, and integrated forecasting, empowering leadership teams to make data-driven decisions on sales prioritization, market expansion, and resource allocation.

## 2. Objectives and Success Criteria

### Objectives
1. **SVR-RM Revenue & Top Customers**  
   - Unify SKU-level sales inputs, customer hierarchies, and enrichment tables so SVR-RM T1/T2/T3 cohorts and top-account breakouts flow end-to-end from ingestion to dashboards.  
   - Train and operationalize quarterly SARIMAX forecasts that expose point estimates plus confidence bands for each SVR-RM tier and top-customer slice.  
   - Publish forecast outputs and health metrics into Metabase collections used by executive sales planning.  
   - **Primary warehouse artifact:** `analytics.forecast_overall`  
     (`forecast_run_id`, `cohort`, `model_name`, `model_version`, `sku`, `channel`,  
     `sale_month`, `forecast_date`, `forecast_quantity`, `forecast_revenue`,  
     `forecast_revenue_lower`, `forecast_revenue_upper`, `actual_quantity`,  
     `actual_revenue`, `product_name`, `product_type`, `product_subcategory`,  
     `created_at`).

2. **Synology C2 Exploratory Analysis**  
   - Profile cloud service adoption (C2 Storage, Backup, Surveillance) by region, customer tier, and SKU using the consolidated sale-out snapshot to uncover expansion signals.  
   - Deliver subscription-oriented metrics (customer counts, order velocity, revenue, seat proxies) derived from sales activity, with telemetry/support enrichments earmarked for a future phase.  
   - Package findings into Metabase narratives and sandbox notebooks that feed the broader commercial playbooks for C2 growth.  
   - **Primary warehouse artifact:** `analytics.c2_adoption_scorecard`  
     (`snapshot_month`, `service_family`, `plan_variant`, `region`, `customer_tier`,  
     `sku`, `active_subscriptions`, `new_subscriptions`, `arr_usd`, `total_quantity`,  
     `avg_seats`).

3. **Consumer Trend & Commercial Activation**  
   - Maintain a unified BI architecture (dbt → Postgres → Metabase) that blends execution KPIs, competitive intelligence, and forecast outputs for commercial storytelling.  
   - Surface campaign-ready insights, scenario comparisons, and business-case templates that leverage the forecast artifacts.  
   - Equip stakeholders with automated reporting flows and governance so decisions are backed by consistent metrics across sales, marketing, and finance.  
   - **Primary warehouse artifact:** `analytics.activation_storylines`  
     (`snapshot_month`, `region`, `segment`, `actual_revenue`, `forecast_revenue`,  
     `variance_pct`, `inventory_weeks_cover`, `market_index_score`, `activation_score`,  
     `recommended_action`, `confidence_note`).

### Success Metrics
| Metric | Target |
| --- | --- |
| Forecast accuracy improvement | >= +15% vs manual baseline |
| Multiple linear regression error (MAPE) | Meets agreed KPI threshold |
| Next-quarter forecast coverage | 100% of priority product & channel segments |
| Dashboard adoption rate | >= 80% of regional users monthly |
| Reporting latency reduction | 30% faster refresh cycles |
| Business case turnaround time | Reduced from 5 days -> 1 day |
| Executive satisfaction score | >= 4.5 / 5 on quarterly feedback |

## 3. Scope of Work

### In Scope
- Data transformation and modeling using **dbt (Data Build Tool)**, SQL, and Python to create modular, version-controlled models in a star-schema architecture for sales and marketing data.
- Centralized warehouse storage on **Synology NAS Postgres** with optional cloud-read replica if needed for external stakeholders.
- Docker-based orchestration and automation for ETL, model retraining, and dashboard refresh workflows using **Apache Airflow (primary)** and **n8n (secondary)** hosted on Synology NAS.
- Dashboard design and deployment in **Metabase**, connected to the Postgres warehouse.
- Predictive model creation (next-quarter sales forecasting, opportunity identification) with emphasis on SVR-RM T1/T2/T3 (overall + top customers), Synology C2 exploratory insights, and commercial activation storytelling.
- Maintenance of full-catalog marts so Metabase users can explore beyond the SVR focus while forecasts remain SKU-specific.
- Development of a forecasting and prioritization analytical framework.
- Business case automation templates for marketing strategy.

### Out of Scope
- Data ingestion (raw data provided at project start).
- Versioning, DevOps, and CI/CD workflows.
- Monitoring and QA systems.
- CRM software customization.
- Manual data entry or unstructured feedback collection.
- Third-party licensing negotiations for syndicated data.

## 4. System Architecture

### Data Sources
| Type | Description | Refresh Frequency |
| --- | --- | --- |
| CRM (HubSpot/Internal) | Leads, conversions, customer segmentation | Daily |
| ERP (Sell-in Data) | Shipments to distributors | Weekly |
| Distributor POS | Sell-through and inventory levels | Weekly |
| Digital Campaign Data | Google Ads and Meta Ads metrics | Daily |
| Customer Feedback | NPS and support tickets | Monthly |
| Competitive Intelligence | Market share reports and pricing | Quarterly |

### Data Flow Overview
```
          ┌──────────────────┐
          │   Raw Data Files │  (CRM, ERP, Campaigns, etc.)
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │ Airflow / n8n    │   (Scheduler & Orchestration)
          │ - DAGs, ETL Jobs │
          │ - Triggers       │
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │  dbt + Postgres  │   (Data Transformation & Modeling)
          │ - Cleaned Tables │
          │ - Fact/Dim Schema│
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │     Metabase      │   (Visualization Layer)
          │ - Connects via SQL│
          │ - Dashboards      │
          └──────────────────┘
```

### Data Flow Summary
- **Transformation & Modeling:** SQL and Python logic, orchestrated through **dbt** and Airflow, clean, aggregate, and structure datasets into a star-schema optimized for analytical queries. dbt manages dependencies, documentation, and model lineage for transparency.
- **Storage & Warehouse:** The on-prem Synology Postgres instance serves as the primary data warehouse, with optional cloud replication for redundancy. Data encryption at rest and nightly NAS snapshots ensure integrity.
- **Orchestration & Automation:** All ETL, model refresh, and dashboard refresh tasks orchestrated via Airflow (for data pipelines and dbt jobs) and n8n (for API automation and Metabase dashboard refreshes) running in Docker containers on Synology NAS.
- **Visualization:** Metabase connects directly to the Postgres warehouse via secure network tunnel. Dashboards are refreshed via Metabase scheduling or triggered via n8n/Airflow API calls.

## 5. Core Deliverables
| Deliverable | Description | Owner |
| --- | --- | --- |
| Unified Data Warehouse | Centralized Postgres database on Synology integrating all sources | Data Engineering |
| Forecasting Model | Predictive model estimating quarterly sales by region and SKU | BI Lead |
| KPI Framework | Three-tier KPI hierarchy (Strategic, Tactical, Operational) | BI Lead |
| Metabase Dashboards | Executive view and regional performance dashboards | BI Analyst |
| Competitive Index | Market share and price competitiveness tracker | Strategy Team |
| Business Case Generator | Metabase templates for ROI modeling and scenario planning | Marketing Analytics |
| dbt Model Repository | Modular SQL and YAML definitions with documentation and lineage tracking | Data Engineering |

## 6. Predictive Modeling Specification

### Model Type
Multiple linear regression optimized for Synology sale-out data with a mean absolute percentage error (MAPE) held within the agreed tolerance.

### Input Features
- Historical sale-out data (two-year rolling window).
- Campaign spend and conversion rate.
- Distributor inventory levels.
- Region-level seasonality.
- Competitive pricing index.

### Output
- Forecasted quarterly sales volume per SKU and region.
- Confidence interval (95%).
- Growth opportunity heatmap.

### Performance Metrics
- Mean Absolute Percentage Error (target per KPI baseline).
- Rolling four-quarter RMSE comparison.
- Scenario variance simulation.

## 7. Reporting and Visualization Framework

### Dashboard Layers
- Executive Forecasting Board: Forecast accuracy, regional trends, and performance versus targets.
- Commercial Pulse Dashboard: Sales, CRM, and marketing KPIs with drilldowns.
- Opportunity Radar: Market opportunity identification using forecast and competitive signals.
- Campaign ROI Tracker: Spend efficiency and pipeline contribution.

### Dashboard Standards
- Unified color palette and metric definitions.
- Automated refresh schedule (daily and weekly).
- Embedded data dictionary and annotation fields.
- Hosted in Metabase, connected directly to Postgres for live or scheduled queries.

## 8. Forecasting and Prioritization Framework

### Logic
- Map funnel stages to KPIs: Awareness -> Consideration -> Conversion -> Retention -> Advocacy.
- Apply weighted scoring to assess the impact of reallocating marketing or sales budgets.
- Provide a scenario simulator for ROI sensitivity.

### Example Use Case
Reallocating 10% of marketing spend from awareness to retention in APAC delivers an estimated +6% increase in recurring revenue with a flat budget.

## 9. Business Case Support
- Deliver a data-driven business case generator that auto-populates with the latest market and forecast data.
- Support what-if scenarios across launch, channel, and pricing levers.
- Export executive-ready PowerPoint decks.
- Primary users: Regional marketing managers and product owners.
- Outcome: Consistent, faster decision-making with aligned KPI targets.

## 10. Stakeholders
| Role | Department | Responsibility |
| --- | --- | --- |
| BI Lead | Commercial Strategy | Project ownership and modeling oversight |
| Data Engineer | IT and Data Platform | Pipeline development, dbt modeling, and data validation |
| Marketing Analytics | Marketing | Campaign data integration and ROI modeling |
| Regional Sales Managers | Sales | Forecast input and KPI feedback |
| Executives | HQ Leadership | Strategic decisions and prioritization |

## 11. Project Timeline
| Phase | Milestone | Duration |
| --- | --- | --- |
| Phase 1 | Data integration and dbt model setup | 4 weeks |
| Phase 2 | Model development and validation | 6 weeks |
| Phase 3 | Dashboard design and deployment | 4 weeks |
| Phase 4 | Forecasting and business case automation | 4 weeks |
| Phase 5 | User training and adoption rollout | 2 weeks |

**Total Estimated Duration:** 20 weeks (5 months)

## 12. Risks and Mitigation
| Risk | Impact | Mitigation |
| --- | --- | --- |
| Inconsistent data definitions across regions | High | Establish a KPI glossary and unified data model early in the project. |
| API rate limits from marketing platforms | Medium | Implement batch data fetch with caching. |
| Low dashboard adoption | Medium | Conduct training sessions and capture feedback for iteration. |
| Forecast model overfitting | Medium | Apply rolling-window cross-validation. |
| dbt model dependency errors | Medium | Enforce dependency graph validation and CI checks before deployments. |
| Connection reliability between Metabase and Postgres | Medium | Configure SSL/tunnels + periodic health checks for stable refreshes. |

## 13. Expected Outcomes
| Dimension | Expected Result |
| --- | --- |
| Data Quality | Unified data sources across CRM, ERP, and campaign systems. |
| Efficiency | Automated ETL, dbt transformation, and dashboard updates via Airflow/n8n. |
| Forecasting | +18% accuracy improvement versus the manual baseline. |
| Strategic Impact | Improved prioritization of high-margin regions. |
| Cultural Impact | Stronger alignment between marketing, sales, and BI teams. |
