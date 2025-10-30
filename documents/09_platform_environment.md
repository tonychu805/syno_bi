# Platform Environment Implementation Guide

## Objective
Stand up a reproducible container environment on the Synology NAS that runs Airflow, dbt, n8n, and supporting services required for the Synology BI platform.

## Responsibilities
- Provision Docker images and compose configuration for orchestration, transformation, and automation workloads.
- Standardize environment variables, secrets storage, and network topology so services communicate securely.
- Document build/deploy procedures and lifecycle tasks (start, stop, upgrade, backup).

## Runtime Components
- **Airflow**: Scheduler, webserver, worker, and triggerer containers sharing a common metadata database.
- **dbt Runner**: Lightweight container image (Python 3.11) with dbt-core + dbt-postgres installed; invoked via Airflow tasks.
- **n8n**: Automation layer handling Metabase API calls, webhook handling, and alert routing.
- **Metabase**: BI visualization application served from the NAS, connecting securely to Supabase.
- **Supabase Connectivity**: Managed Postgres in the cloud accessed via secure network tunnel (VPN or IP allowlist).
- **Supporting Services**: Redis or Celery backend (if required), PostgreSQL metadata database for Airflow (can be NAS-hosted), and shared volumes for logs/artifacts.

## Directory Layout (NAS)
```
/volume1/docker/syno_bi/
├── repo/                    # Git checkout of syno_prediction
│   ├── dags/
│   ├── dbt/
│   ├── documents/
│   ├── infra/
│   ├── env/
│   │   ├── airflow.env          # Airflow-specific environment variables
│   │   ├── dbt.env              # dbt runner variables (Supabase creds, profiles dir)
│   │   ├── metabase.env         # Metabase application configuration (metastore DB)
│   │   └── n8n.env              # Webhook secrets, Metabase API tokens
│   └── docker-compose.yml (optional runtime copy)
├── airflow/
│   ├── dags/                # Mounted from repo `dags/`
│   ├── logs/                # Persisted Airflow logs
│   └── plugins/             # Optional custom operators
├── dbt/
│   ├── project/             # Mounted from repo `dbt/`
│   └── target/              # dbt compilation targets
├── n8n/
│   └── data/                # Workflow state and credentials
└── docker-compose.yml       # Deployed compose file (copied from repo/infra)
```

## Environment Variables
- `SUPABASE_HOST`, `SUPABASE_DB`, `SUPABASE_USER`, `SUPABASE_PASSWORD`: shared across Airflow/dbt containers.
- `MB_DB_HOST`, `MB_DB_DBNAME`, `MB_DB_USER`, `MB_DB_PASS`, `MB_ENCRYPTION_SECRET_KEY`: configure the Metabase application database (defaults provided in `metabase.env`).
- `METABASE_HOST`, `METABASE_API_TOKEN`, `N8N_METABASE_WEBHOOK`: consumed by n8n automations if triggering Metabase dashboard refreshes via API or webhooks.
- `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__CORE__SQL_ALCHEMY_CONN`, `AIRFLOW__WEBSERVER__SECRET_KEY`: Airflow metadata and security.
- `SYNOBI_REPO_ROOT`: mounted path pointing to the Git checkout for DAG/static assets.
- Store non-public variables in Synology secrets vault or `.env` files protected by NAS permissions.

## Deployment Steps
1. **Prep NAS**: Install Docker package, enable SSH, and allocate storage volume under `/volume1/docker/syno_bi`.
2. **Check Out Repo**: Clone `syno_prediction` to `/volume1/docker/syno_bi/repo` or use Synology Git Server.
3. **Populate Configs**: Copy `dbt/profiles.yml.example` to `dbt/profiles.yml`, fill Supabase credentials, and copy `infra/env/*.env.example` into `repo/env/`, replacing every `CHANGE_ME`. Ensure `infra/postgres/init/create_metabase.sql` matches the Metabase database password (`MB_DB_PASS`).
4. **Author Compose File**: Create `docker-compose.yml` (minimum services shown below) then validate with `docker compose config`.
5. **Bootstrap Airflow**: From `repo/infra/`, run `docker compose up airflow-init` to initialize metadata DB and admin user accounts.
6. **Start Stack**: From `repo/infra/`, run `docker compose up -d` (Airflow scheduler/webserver/worker, dbt runner, n8n, Metabase). Confirm health via UI and logs.
7. **Register Connections**: In Airflow UI, configure Supabase connections and store Metabase API credentials (if refreshes are triggered via API); import n8n workflows pointing to Airflow webhooks if needed.
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
  airflow-scheduler:
    image: apache/airflow:2.8.1-python3.11
    env_file:
      - ./env/airflow.env
    depends_on:
      - airflow-webserver
      - postgres
      - redis
    volumes:
      - ./repo/dags:/opt/airflow/dags
      - ./repo/dbt:/opt/airflow/dbt
      - ./airflow/logs:/opt/airflow/logs
    command: scheduler

  airflow-webserver:
    image: apache/airflow:2.8.1-python3.11
    env_file:
      - ./env/airflow.env
    ports:
      - "8080:8080"
    volumes:
      - ./repo/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
    command: webserver

  dbt-runner:
    image: ghcr.io/dbt-labs/dbt-postgres:1.7.11
    env_file:
      - ./env/dbt.env
    volumes:
      - ./repo/dbt:/usr/app/dbt
    entrypoint: ["sleep", "infinity"]

  n8n:
    image: n8nio/n8n:1.36
    env_file:
      - ./env/n8n.env
    ports:
      - "5678:5678"
    volumes:
      - ./n8n/data:/home/node/.n8n

  metabase:
    image: metabase/metabase:v0.49.14
    env_file:
      - ./env/metabase.env
    ports:
      - "3000:3000"
    volumes:
      - ./metabase/data:/metabase-data
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: ${AIRFLOW_DB_PASSWORD}
      POSTGRES_DB: airflow
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no
```

> Note: On Synology DSM, use `docker compose` (plugin) or `docker-compose` binary as available. Ensure the repo volume is mounted read-only for production DAG execution.

## Operational Guidelines
- **Backups**: Schedule nightly snapshots of `airflow/logs`, `n8n/data`, and Postgres volumes; export dbt manifests to S3/NAS archive.
- **Upgrades**: Test new Airflow/dbt images in staging; use rolling upgrades (stop scheduler last) and validate DAG compatibility.
- **Secrets Management**: Rotate Supabase/Metabase tokens quarterly; restrict env files to NAS admin group.
- **Monitoring**: Publish Airflow metrics to Prometheus/Grafana or Synology Resource Monitor; configure email/Slack alerts via Airflow + n8n.

## Deliverables & Checkpoints
- `docker-compose.yml` committed (excluding secrets) with README instructions.
- Successful Airflow + dbt + n8n stack running on NAS staging environment.
- Runbook documenting backup/restore, upgrades, and failure triage.
