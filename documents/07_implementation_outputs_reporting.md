# Outputs & Reporting Implementation Guide

## Objective
Communicate model results, business insights, and operational status through curated outputs that stakeholders can interpret and trust.

## Responsibilities
- Produce standardized forecast tables, charts, and commentary each run
- Maintain documentation linking metrics to decisions and downstream consumers
- Host interactive dashboards in Metabase with governed access controls
- Ensure outputs are versioned, timestamped, and reproducible

## Inputs & Outputs
- Inputs: Forecast artifacts, evaluation metrics, business calendar metadata
- Outputs: `documents/reports/` summaries, visualizations, CSV extracts for stakeholders, slide-ready tables

## Implementation Steps
1. Define report templates (Markdown, HTML, or notebook exports) capturing key metrics and narratives
2. Configure Metabase collections/dashboards, ensuring connections to Supabase marts and applying row-level permissions
3. Automate report generation post-forecast run, embedding charts (matplotlib/plotly) and tables
4. Trigger Metabase dashboard cache refreshes through Airflow or n8n (using `N8N_METABASE_WEBHOOK` or direct API calls) and store static outputs with semantic filenames (date + model version), updating the changelog
5. Provide stakeholder distribution plan (email, shared drive, Metabase subscriptions)

## Testing & Validation
- Snapshot tests for report templates to avoid unintended layout regressions
- Data reconciliation comparing reported numbers vs source artifacts
- Manual QA checklist for first releases, transitioning to automated assertions

## Tooling & Dependencies
- Metabase for dashboard delivery and subscriptions; Supabase as the data source
- matplotlib/plotly/seaborn for visualization; jinja2 or nbconvert for templated reports
- Metabase API (e.g., /api/dashboard/:id/public_link) invoked via Airflow/n8n; Markdown/HTML renderers and CLI wrappers

## Risks & Mitigations
- Report drift: maintain contract tests and review loops with stakeholders
- Sensitive data exposure: apply masking rules, Metabase data permissions/row-level security, and redact PII before distribution

## Deliverables & Checkpoints
- Report generation scripts with documentation and scheduling instructions
- Sample report stored in documents/reports/ with acceptance sign-off
- Distribution roster and SLA documented for analytics & business teams
