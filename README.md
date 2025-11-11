# Synology BI Forecasting & Adoption Platform

This repository documents and operationalizes Tony Chu's Synology BI initiative: a unified data platform that ingests global sale-out snapshots, standardizes them in dbt, and publishes SVR-RM and Synology C2 insights through Airflow, Metabase, and executive-ready narratives. It exists to showcase BI manager-level leadership across data strategy, forecasting, and commercialization, anchored to the requirements in `documents/strategy/PRD.md` and the implementation plan in `documents/implementation/summary.md`.

---

## Architecture at a Glance
- **Ingestion & Feature Prep** – Python 3.11 modules under `src/ingestion/` and `src/forecasting/` convert raw Excel workbooks into curated datasets and forecasting features (pandas, statsmodels, scikit-learn, xgboost).
- **Transformation** – dbt project in `dbt/` materializes staging + mart models inside Postgres (`analytics` schema) following the reference playbook in `documents/reference/data_pipeline_reference.md`.
- **Orchestration** – Apache Airflow DAGs in `dags/` orchestrate ingestion → dbt → forecasting → dashboard refresh. Supporting services (Redis, Postgres, n8n) are wired via `docker-compose.yml` and `Dockerfile.airflow`.
- **Analytics Delivery** – Metabase, pgAdmin, and notebook exports inside `notebook_outputs/` deliver curated scorecards, while notebooks in `notebook/` document exploratory work with README + export plans per the agent instructions.
- **Governance & Quality** – Tests live beside code in `tests/`, CI (`.github/workflows/ci.yml`) enforces lint/pytest/dbt compile, and documents in `documents/` trace requirements, phases, and strategy decisions.

---

## Repository Tour
| Path | Purpose |
| --- | --- |
| `documents/` | Strategy (`strategy/`), implementation phases (`implementation/phases/`), and reference guides for the BI roadmap. Start with `documents/implementation/summary.md`. |
| `raw/` & `data/raw/` | Read-only Excel snapshots delivered by Synology. Never edit in place; downstream code writes into `data/processed/`. |
| `src/` | Production Python packages (ingestion + forecasting). Modules mirror domains so tests can align (`tests/forecasting/`, `tests/ingestion/`). |
| `dags/` | Airflow DAGs (`syno_c2_adoption`, `syno_forecast_region`, etc.) plus shared helpers in `dags/utils.py`. |
| `dbt/` | dbt project (profiles, models, macros, seeds) that shapes the warehouse schema consumed by forecasts and dashboards. |
| `env/` | Example env files for Airflow, dbt, Metabase, pgAdmin, n8n. Copy to real `.env` files outside source control. |
| `infra/` | Persistent Docker volumes (Postgres, Metabase, Airflow logs/plugins) for Synology NAS deployments. |
| `notebook/` & `notebook_outputs/` | Exploratory analysis and exported artifacts backing stakeholder storytelling. |
| `tests/` | Pytest suites mirroring `src/` packages with lightweight fixtures and README guidance. |

---

## Getting Started
1. **Prerequisites**
   - Python 3.11, Docker + Docker Compose, and GNU Make (optional).
   - Access to Synology sale-out workbooks placed under `raw/`.
2. **Clone & Environment**
   ```bash
   git clone <repo-url>
   cd syno_prediction
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Environment Variables**
   - Copy each `env/*.env.example` to `env/*.env` and fill in secrets (Postgres, Airflow, Metabase, alert recipients). Keep real credentials out of Git.
   - Point `dbt/profiles.yml` (or the mounted copy) at your warehouse.

---

## Running the Stack (Docker Compose)
1. Build/init Airflow metadata and admin:
   ```bash
   docker compose run --rm airflow-init
   ```
2. Start core services (Airflow webserver/scheduler/worker/triggerer, Postgres, Redis, Metabase, dbt runner, n8n, pgAdmin):
   ```bash
   docker compose up -d
   docker compose ps
   ```
3. Access consoles:
   - Airflow: `http://localhost:8080` (default admin/admin unless overridden).
   - Metabase: `http://localhost:3000`.
   - dbt docs: `http://localhost:8081` (after `docker compose up -d dbt-docs`).
   - pgAdmin: `http://localhost:5050`.
4. Trigger pipelines: In Airflow trigger `syno_c2_adoption`, `syno_forecast_region`, `syno_forecast_svr_rm`, or `syno_ingestion`. Logs live under `infra/airflow/logs`.
5. Stop services when finished:
   ```bash
   docker compose down
   ```

---

## Local Development Workflow
1. **Code updates** in `src/`, `dags/`, or `dbt/` following documented phases.
2. **Unit tests & linting** before committing:
   ```bash
   pytest --maxfail=1 -q
   ruff check src tests
   black src tests
   ```
   - Target ≥80% coverage (`pytest --cov=src --cov-report=term-missing`).
3. **dbt validation** (inside container or local profile):
   ```bash
   docker compose exec dbt-runner bash -lc "dbt deps && dbt run --select staging+ && dbt test --select staging+"
   ```
4. **Airflow dry runs**: Use `airflow dags test syno_c2_adoption <execution_date>` inside the Airflow container when validating DAG changes.
5. **Conventional Commits** summarize one concern at a time (e.g., `feat: add c2 retention mart`).

---

## Data Lifecycle & Governance
- `raw/` snapshots are immutable. Ingestion scripts output sanitized CSV/Parquet to `data/processed/ingestion/` while preserving schema fidelity.
- dbt staging + marts enforce naming, typing, and ownership metadata; update `schema.yml` files whenever columns change.
- Forecast artifacts and scorecards land in `data/processed/forecasts/` and `notebook_outputs/` with timestamps for traceability.
- Secrets stay in `.env` files ignored by Git. Rotate database credentials regularly and review `documents/implementation/phases/06_quality_gates.md` for lint/test coverage standards.

---

## Documentation & Playbooks
- **Strategy & PRD** – `documents/strategy/PRD.md` plus `documents/strategy/data_analytics_playbook.md` define stakeholder goals, success metrics, and BI leadership framing.
- **Implementation Phases** – Each numbered guide in `documents/implementation/phases/` outlines expectations for ingestion, preprocessing, feature engineering, forecasting, pipelines, quality gates, reporting, and ops.
- **Reference Guides** – `documents/reference/data_pipeline_reference.md` captures the end-to-end workflow (raw → Airflow/dbt → Metabase) and the command catalog.

Always link pull requests back to the relevant phase note and strategy artifact so reviewers understand business intent.

---

## Troubleshooting
- **Airflow task fails inserting `analytics.c2_retention.active_logos`** – Ensure the warehouse table has the `active_logos` column (run the corresponding dbt migration) before rerunning `syno_c2_adoption`. Logs reside in `infra/airflow/logs/...`.
- **dbt profile errors** – Confirm `dbt/profiles.yml` (mounted into containers) matches the credentials defined in `env/dbt.env`.
- **Metabase cannot see tables** – Verify Postgres is healthy (`docker compose ps`) and dbt has published the required marts; refresh the database schema inside Metabase settings.
- **Notebook drift** – Regenerate outputs under `notebook_outputs/` after rerunning notebooks, and document export-to-module plans per the repository guidelines.

---

## Contributing Checklist
1. Read the relevant phase note and PRD section.
2. Update code/models/docs plus add/adjust tests.
3. Run `pytest`, `ruff check`, `black`, and `dbt run/test` if applicable.
4. Capture impacts (dashboards, tables, KPIs) in PR descriptions, citing `documents/implementation/phases/<phase>.md`.
5. Request review from both a data scientist and analytics engineer when touching ingestion or forecasting logic.

By following this README, contributors can confidently extend the Synology BI platform while aligning each change to the strategic roadmap and quality expectations.
