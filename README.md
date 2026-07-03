# Elith

Config-driven multi-tenant RAG chat platform. The current implementation covers
the standard RAG flow plus the A-company sample scenario: citation-required
answers, source warnings, answer modes, feedback, review candidates, and local
sample data.

## Local Setup

Start PostgreSQL with pgvector:

```bash
docker compose up -d db
```

Install and migrate the backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
DATABASE_URL=postgresql+psycopg://elith:elith@127.0.0.1:5432/elith alembic upgrade head
```

Seed the A-company sample tenant, tenant_config, and FAQ document:

```bash
DATABASE_URL=postgresql+psycopg://elith:elith@127.0.0.1:5432/elith python scripts/seed_shinonome.py
```

The seed command prints `tenant_id=<number>`. Use that value for local frontend
requests.

Run the API:

```bash
ENVIRONMENT=local \
DATABASE_URL=postgresql+psycopg://elith:elith@127.0.0.1:5432/elith \
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the web app:

```bash
cd web
npm install
cp .env.example .env.local
# set NEXT_PUBLIC_LOCAL_TENANT_ID to the seed output
npm run dev
```

Open `http://localhost:3000`.

## Local Verification

API health:

```bash
curl -s http://127.0.0.1:8000/health
```

Tenant config:

```bash
curl -s -H "X-Tenant-ID: <tenant_id>" http://127.0.0.1:8000/tenant/config
```

Chat:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <tenant_id>" \
  -d '{"query":"請求書の再発行はできますか","mode":"external"}' \
  http://127.0.0.1:8000/chat
```

Feedback and review:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <tenant_id>" \
  -d '{"answer_id":1,"rating":"bad","reason_category":"古い根拠","comment":"旧資料を参照"}' \
  http://127.0.0.1:8000/feedback

curl -s -H "X-Tenant-ID: <tenant_id>" http://127.0.0.1:8000/review
```

## Test Commands

Backend:

```bash
cd backend
ruff check
ruff format --check
DATABASE_URL=postgresql+psycopg://elith:elith@127.0.0.1:5432/elith \
  python -m pytest -p no:cacheprovider
```

Frontend:

```bash
cd web
npm run lint
npm run test
npx tsc --noEmit --incremental false
npm run build
```

## Environment Variables

Backend:

| Name | Purpose | Local example |
|---|---|---|
| `ENVIRONMENT` | Provider and local tenant-header behavior | `local` |
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL | `postgresql+psycopg://elith:elith@127.0.0.1:5432/elith` |
| `GEMINI_API_KEY` | Optional Gemini key; empty uses mock provider | empty |
| `LOG_LEVEL` | API log level | `INFO` |

Frontend:

| Name | Purpose | Local example |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI base URL | `http://localhost:8000` |
| `NEXT_PUBLIC_LOCAL_TENANT_ID` | Local-only `X-Tenant-ID` fallback | seed output |

Do not commit real secrets. Local dummy database credentials are for developer
machines only.

## GCP Target Architecture

The production-oriented target is Cloud Run for web/API, Cloud SQL PostgreSQL
with pgvector for relational and vector data, Cloud Storage for raw source
materials, Secret Manager for provider/database secrets, and Cloud Logging for
runtime logs.

```mermaid
flowchart LR
  U[User] --> W[Cloud Run: Next.js web]
  W --> A[Cloud Run: FastAPI api]
  A --> SQL[(Cloud SQL PostgreSQL + pgvector)]
  A --> GCS[(Cloud Storage source files)]
  A --> LLM[LLM / Embedding Provider]
  A --> SM[Secret Manager]
  A --> LOG[Cloud Logging]
```

### Containerization

- `infra/Dockerfile.api` builds the FastAPI backend.
- `infra/Dockerfile.web` builds the Next.js frontend.
- Cloud Run services stay stateless. All durable state lives in Cloud SQL or
  Cloud Storage.

### Data

- Tenant, tenant_config, document, chunk, answer, citation, and feedback rows
  live in Cloud SQL.
- Vector search uses pgvector in the same database to keep the MVP operationally
  small.
- Raw PDFs or source files should be stored in Cloud Storage; indexed chunks and
  metadata are stored in PostgreSQL.

### Secrets

- `DATABASE_URL`, provider API keys, and production-only runtime values should
  be injected from Secret Manager.
- Never log full API keys, database URLs with passwords, or source document
  contents when handling provider failures.

### Logs

- API and web container logs go to Cloud Logging.
- Useful filters: Cloud Run service name, request path (`/chat`, `/documents`,
  `/feedback`), status code, and tenant id metadata if later added safely.

### Cost Controls

- Start with minimum Cloud Run instances set to 0 for non-production.
- Use Cloud SQL small instances for MVP data volume.
- Keep mock provider available for demos that do not need real LLM calls.
- Monitor provider usage separately from Cloud Run/Cloud SQL costs.

### Deploy Outline

1. Build and push API and web container images.
2. Provision Cloud SQL with pgvector enabled.
3. Run Alembic migrations against Cloud SQL.
4. Configure Secret Manager values.
5. Deploy API Cloud Run service with backend env vars.
6. Deploy web Cloud Run service with `NEXT_PUBLIC_API_BASE_URL` pointing to API.
7. Seed tenant_config through an admin path or a controlled one-off job.
8. Verify `/health`, `/tenant/config`, `/chat`, `/feedback`, and `/review`.

### Rollback / Incident Response

- Roll back Cloud Run to the previous revision if a release breaks request
  handling.
- If provider failures spike, unset the provider key or switch the runtime to
  mock for temporary local/demo recovery.
- If a bad tenant_config causes errors, restore the previous config row value or
  disable the affected pipeline step in that tenant's config.
- Do not run destructive database operations as part of rollback.
