# Project Requirement Document (PRD)

## Project Title
Synology Global BI Platform - Sales Forecasting & Market Intelligence Framework

## 1. Project Overview

The Synology Global BI Platform is a strategic initiative designed to unify disparate data sources across regional sales, marketing, and distribution channels into a single analytical ecosystem. It aims to deliver actionable insights through automated dashboards, predictive modeling, and integrated forecasting, empowering leadership teams to make data-driven decisions on sales prioritization, market expansion, and resource allocation.

## 2. Objectives and Success Criteria

### Objectives
- Integrate multiple internal and external data sources into a single BI architecture.
- Develop and deploy predictive models to forecast sales volumes and product demand.
- Provide commercial and marketing teams with a unified view of execution KPIs, competitive intelligence, and market dynamics.
- Support the creation of data-backed business cases for new product launches and regional investments.

### Success Metrics
| Metric | Target |
| --- | --- |
| Forecast accuracy improvement | >= +15% vs manual baseline |
| Multiple linear regression error (MAPE) | <= 2% |
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
- Predictive model creation (sales forecasting, opportunity identification).
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
Multiple linear regression optimized for Synology sale-out data with a target mean absolute percentage error (MAPE) of 2% or lower.

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
- Mean Absolute Percentage Error (target ≤2%).
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
