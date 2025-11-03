# Platform Environment Implementation Guide

## Objective
Stand up a reproducible container environment on the Synology NAS that runs Airflow, dbt, n8n, and supporting services required for the Synology BI platform.

## Responsibilities
- Provision Docker images and compose configuration for orchestration, transformation, and automation workloads.
- Standardize environment variables, secrets storage, and network topology so services communicate securely.
- Document build/deploy procedures and lifecycle tasks (start, stop, upgrade, backup).
- Guarantee the environment supports the quarterly forecasting pipeline, including storage for next-quarter outputs and evaluation logs.

## Runtime Components
- **Airflow**: Scheduler, webserver, worker, and triggerer containers sharing a common metadata database.
- **dbt Runner**: Lightweight container image (Python 3.11) with dbt-core + dbt-postgres installed; invoked via Airflow tasks.
- **dbt Docs**: Companion container that generates and serves dbt documentation on port 8081 for on-prem browsing.
- **n8n**: Automation layer handling Metabase API calls, webhook handling, and alert routing.
- **Metabase**: BI visualization application served from the NAS, connecting securely to the on-prem Postgres warehouse.
- **Warehouse Postgres**: Stateful Postgres service hosted in Docker (see `postgres` container) storing staging and mart schemas for dbt, Airflow, and Metabase.
- **Supporting Services**: Redis or Celery backend (if required), PostgreSQL metadata database for Airflow (can be NAS-hosted), and shared volumes for logs/artifacts.

## Directory Layout (NAS)
```
/volume1/docker/syno_bi/
├── repo/                    # Git checkout of syno_prediction
│   ├── docker-compose.yml   # Uses ./env/*.env for secrets
│   ├── env/
│   │   ├── airflow.env      # Airflow-specific environment variables
│   │   ├── dbt.env          # dbt runner variables (Postgres warehouse creds)
│   │   ├── metabase.env     # Metabase application configuration
│   │   └── n8n.env          # Webhook secrets, Metabase API tokens
│   ├── infra/
│   │   ├── airflow/
│   │   │   ├── logs/
│   │   │   └── plugins/
│   │   ├── metabase/data/
│   │   ├── n8n/data/
│   │   └── postgres/
│   │       ├── data/
│   │       └── init/
│   ├── dags/
│   ├── dbt/
│   └── documents/
└── docker-compose.yml       # Optional runtime copy (mirrors repo version)
```

## Environment Variables
- `WAREHOUSE_HOST`, `WAREHOUSE_DB`, `WAREHOUSE_USER`, `WAREHOUSE_PASSWORD`: shared across Airflow/dbt containers; defaults point to the internal `postgres` service.
- `MB_DB_HOST`, `MB_DB_DBNAME`, `MB_DB_USER`, `MB_DB_PASS`, `MB_ENCRYPTION_SECRET_KEY`: configure the Metabase application database (defaults provided in `metabase.env`).
- `METABASE_HOST`, `METABASE_API_TOKEN`, `N8N_METABASE_WEBHOOK`: consumed by n8n automations if triggering Metabase dashboard refreshes via API or webhooks.
- `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__CORE__SQL_ALCHEMY_CONN`, `AIRFLOW__WEBSERVER__SECRET_KEY`: Airflow metadata and security.
- `SYNOBI_REPO_ROOT`: mounted path pointing to the Git checkout for DAG/static assets.
- Store non-public variables in Synology secrets vault or `.env` files protected by NAS permissions.

## Deployment Steps
1. **Prep NAS**: Install Docker package, enable SSH, and allocate storage volume under `/volume1/docker/syno_bi`.
2. **Check Out Repo**: Clone `syno_prediction` to `/volume1/docker/syno_bi/repo` or use Synology Git Server.
3. **Populate Configs**: Copy `dbt/profiles.yml.example` to `dbt/profiles.yml`, fill Postgres warehouse credentials, and copy `env/*.env.example` to `env/*.env`, replacing every `CHANGE_ME`. Ensure `infra/postgres/init/create_metabase.sql` matches the Metabase database password (`MB_DB_PASS`).
4. **Author Compose File**: Use the repo root `docker-compose.yml` (minimum services shown below) and validate with `docker compose config`.
5. **Bootstrap Airflow**: `cd /volume1/docker/syno_bi/repo && docker compose up airflow-init` to initialize metadata DB and admin user accounts.
6. **Start Stack**: From the same directory, run `docker compose up -d` (Airflow scheduler/webserver/worker, dbt runner, dbt docs, n8n, Metabase). Confirm health via UI and logs; dbt docs will be available at `http://<nas-host>:8081` once the models compile.
7. **Register Connections**: In Airflow UI, configure Postgres warehouse connections and store Metabase API credentials (if refreshes are triggered via API); import n8n workflows pointing to Airflow webhooks if needed.
8. **Schedule DAG**: Verify `synology_bi_pipeline` loads, update schedule/params as required, and trigger a dry run.

## CI/CD Integration
- Configure GitHub Actions secrets so automated deploys can pull and restart containers on the NAS:
  - `NAS_HOST`: IP or hostname reachable from GitHub runners.
  - `NAS_SSH_PORT`: SSH port (default `22`).
  - `NAS_USER`: NAS user with Docker and repo permissions.
  - `NAS_SSH_KEY`: Private key (PEM) matching the user; store as an encrypted secret.
  - `NAS_PROJECT_PATH`: Absolute path to the repo checkout on the NAS (e.g. `/volume1/docker/syno_bi/repo`).
- The workflow `.github/workflows/ci.yml` runs lint/tests/dbt, then (on pushes to `main`) SSHes into the NAS, runs `git pull`, and restarts the Docker stack via `docker compose up -d`.
- Ensure the NAS user’s shell profile loads Docker/Compose binaries without interactive prompts; otherwise adjust the deploy command or provide a wrapper script.

## Sample docker-compose.yml (Excerpt)
```yaml
version: "3.9"

services:
  airflow-webserver:
    image: apache/airflow:2.8.1-python3.11
    env_file:
      - ./env/airflow.env
    ports:
      - "8080:8080"
    volumes:
      - ./dags:/opt/airflow/dags
      - ./dbt:/opt/airflow/dbt
      - ./infra/airflow/logs:/opt/airflow/logs
      - ./infra/airflow/plugins:/opt/airflow/plugins
    command: webserver
    depends_on:
      - postgres
      - redis

  dbt-runner:
    image: ghcr.io/dbt-labs/dbt-postgres:1.7.11
    env_file:
      - ./env/dbt.env
    volumes:
      - ./dbt:/usr/app/dbt
    command: sleep infinity

  n8n:
    image: n8nio/n8n:1.36
    env_file:
      - ./env/n8n.env
    ports:
      - "5678:5678"
    volumes:
      - ./infra/n8n/data:/home/node/.n8n

  metabase:
    image: metabase/metabase:v0.49.14
    env_file:
      - ./env/metabase.env
    ports:
      - "3000:3000"
    volumes:
      - ./infra/metabase/data:/metabase-data
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: ${AIRFLOW_DB_PASSWORD}
      POSTGRES_DB: airflow
    volumes:
      - ./infra/postgres/data:/var/lib/postgresql/data
      - ./infra/postgres/init:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no
```

> Note: On Synology DSM, use `docker compose` (plugin) or `docker-compose` binary as available. Ensure the repo volume is mounted read-only for production DAG execution.

## Operational Guidelines
- **Backups**: Schedule nightly snapshots of `airflow/logs`, `n8n/data`, and Postgres volumes; export dbt manifests to S3/NAS archive.
- **Upgrades**: Test new Airflow/dbt images in staging; use rolling upgrades (stop scheduler last) and validate DAG compatibility.
- **Secrets Management**: Rotate Postgres/Metabase credentials quarterly; restrict env files to NAS admin group.
- **Monitoring**: Publish Airflow metrics to Prometheus/Grafana or Synology Resource Monitor; configure email/Slack alerts via Airflow + n8n.

## Deliverables & Checkpoints
- `docker-compose.yml` committed (excluding secrets) with README instructions.
- Successful Airflow + dbt + n8n stack running on NAS staging environment.
- Runbook documenting backup/restore, upgrades, and failure triage.
