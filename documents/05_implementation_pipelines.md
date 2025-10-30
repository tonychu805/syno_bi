# Pipeline & Automation Implementation Guide

## Objective
Orchestrate ingestion, preprocessing, feature engineering, and forecasting steps into a repeatable, observable workflow that teams can schedule and monitor.

## Responsibilities
- Package individual modules into an end-to-end Airflow DAG with clear dependencies
- Provide CLI and programmatic entry points for full and incremental runs (Airflow CLI, dbt CLI)
- Instrument logging, error handling, and alerts for proactive operations
- Trigger Tableau Cloud extract/API refreshes once new sale-out outputs land (via n8n or Airflow)

## Inputs & Outputs
- Inputs: Module-level configs, environment variables, orchestration metadata, dbt project files
- Outputs: Airflow run logs, Supabase table refresh status, Tableau Cloud extract refresh confirmations, success/failure notifications

## Implementation Steps
1. Provision Airflow on the Synology NAS (Docker Compose or Kubernetes) with connections for Supabase, Tableau Cloud, and dbt
2. Define DAGs aligning with data availability windows and SLAs: ingestion → dbt run + test → feature/forecast jobs → Tableau refresh
3. Implement centralized config management (YAML + environment overrides) and secrets handling using Airflow Connections/Variables or Vault
4. Integrate dbt operators (`dbt run`, `dbt test`) and PythonOperator tasks for forecasting, capturing lineage metadata
5. Configure n8n automations for Tableau API refreshes, stakeholder notifications, and exception escalations
6. Add observability hooks: logging, metrics (duration, record counts), alert routes (Slack/email) and document operational playbooks plus on-call escalation paths

## Testing & Validation
- Unit tests for task wrappers and error handling paths
- Integration tests executing full pipeline against subset fixtures
- Dry-run mode verifying dependency resolution without writing outputs

## Tooling & Dependencies
- Apache Airflow (primary orchestrator), n8n for API workflows, Docker for containerized deployment
- dbt CLI/operators, python-dotenv for config, logging/structlog
- Tableau Cloud REST API for extract refresh, Supabase client libraries for data loads

## Risks & Mitigations
- Orchestrator complexity: start with minimal viable flow, add features iteratively
- Configuration drift: centralize configs and enforce schema validation

## Deliverables & Checkpoints
- Pipeline entry point documented (`python -m src.pipeline.run` or equivalent)
- Operations runbook stored in documents/
- CI pipeline executing linting, tests, and optional pipeline smoke run
