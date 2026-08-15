# ContractIQ: AI Contract Risk Analyzer

ContractIQ is an enterprise-grade, multi-tenant AI contract risk analyzer and review platform. It automates contract ingestion, chunking, semantic vector indexing, deterministic missing clause detection, clause-by-clause version comparison, precedent clause retrieval, grounded Q&A with citations, human-in-the-loop review trails, PDF risk report generation, and real-time status broadcasting via WebSockets.

---

## 1. Real System Architecture

```text
[ Browser / Next.js 14 Client ]
   |                                 \ (WebSocket: ws://.../contracts/{id}/ws)
   v (HTTP REST API)                  v
+-------------------------------------------------------------------------+
| FastAPI Application Server                                              |
|  ├── Auth & RBAC (Admin / Reviewer / Viewer via JWT)                    |
|  ├── Parameterized RLS Context Injector (set_tenant_context)            |
|  ├── Antivirus Scanner (NoOp / ClamAV EICAR signature scanner)          |
|  ├── Rate Limiting (Redis token-bucket fallback)                        |
|  ├── Grounded LLM Q&A Engine (Groq Llama 3.3 70B with Verbatim Quotes)  |
|  └── WebSocket Realtime Manager (Redis Pub/Sub Subscription)            |
+-------------------------------------------------------------------------+
       |                                   |                    |
       | Dispatches Celery Tasks           | Supabase API       | Publishes Events
       v                                   v                    v
+-----------------------+         +--------------------+ +---------------+
| Celery Workers        |         | Supabase Storage   | | Redis 7       |
|  ├── Text Extraction  |         | (Raw PDFs, DOCX,   | |  ├── Tasks    |
|  ├── Chunking & Embed |         |  Generated PDF     | |  ├── Cache    |
|  ├── Risk Analysis    |         |  Report Artifacts) | |  └── Pub/Sub  |
|  └── PDF Generation   |         +--------------------+ +---------------+
+-----------------------+                   |
       |                                   |
       v (Database Queries via app_user)   |
+-------------------------------------------------------------------------+
| PostgreSQL 16 + pgvector Database Engine                               |
|  ├── FORCE ROW LEVEL SECURITY enabled across all 12 tenant tables       |
|  ├── Relational Schema: users, contracts, versions, findings, etc.      |
|  └── Vector Store: contract_chunks (HNSW index, cosine distance)        |
+-------------------------------------------------------------------------+
```

---

## 2. Why These Technologies?

- **FastAPI (Python 3.12)**: Native async execution for I/O-heavy workloads (S3 downloads, LLM streaming, database queries), auto-generating OpenAPI specs with Pydantic v2 strict type validation.
- **Celery + Redis**: Long-running CPU/network tasks (PDF parsing, embedding generation, ReportLab rendering) run completely off the web request path with exponential backoff retries and idempotent task executions.
- **PostgreSQL 16 with `pgvector`**: Eliminates operational synchronization overhead of separate dedicated vector databases (Pinecone, Qdrant). Relational business data, audit trails, and vector embeddings reside in the same ACID-compliant database under unified Row-Level Security policies.
- **Groq (Llama 3.3 70B Versatile)**: Sub-second inference latency for grounded contract Q&A and clause difference explanations at significantly lower cost than proprietary models, with deterministic fallback when unconfigured.
- **Next.js 14 (App Router) + TailwindCSS**: Modern, responsive dashboard with real-time WebSocket progress bars, side-by-side version diffing, grounded citation viewing, and audit logs.

---

## 3. Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Step 1: Start Infrastructure Containers
```bash
# Starts PostgreSQL (pgvector), Redis, and MinIO
docker compose up -d
```

### Step 2: Configure Environment
```bash
cp .env.example .env
# Fill in optional GROQ_API_KEY for live LLM grounded Q&A (defaults to mock otherwise)
```

### Step 3: Run Database Migrations
```bash
# Runs 10 Alembic migrations, enabling FORCE RLS and creating all 12 domain tables
.venv/bin/alembic upgrade head
# Or on Windows:
.\.venv\Scripts\alembic.exe upgrade head
```

### Step 4: Start Backend & Celery Worker
```bash
# Terminal 1: FastAPI API Server
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery Background Worker
.\.venv\Scripts\celery -A app.workers.celery_app worker -l info
```

### Step 5: Start Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
# Dashboard available at http://localhost:3000
```

---

## 4. Running Tests & Quality Checks

ContractIQ maintains a 297-test regression suite with **87.25% code coverage**:

```bash
# 1. Run full test suite with coverage
.\.venv\Scripts\pytest --cov=app --cov-report=term-missing -v

# 2. Code formatting and linting
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\ruff format --check app tests scripts

# 3. Static type analysis
.\.venv\Scripts\mypy --strict app/

# 4. Frontend typecheck and build validation
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## 5. Current Known Limitations & Architectural Caveats

1. **Observability (`MVP ONLY / LOG-DRIVEN`)**: Structured per-request JSON tracing with correlation IDs (`request_id`, `org_id`, `duration_ms`) is implemented via `structlog`. However, a dedicated Prometheus metrics scraper endpoint (`/metrics`) exposing latency percentiles (p50/p95/p99) and live queue gauges has not yet been implemented.
2. **WebSocket Concurrent Connection Limits (`MVP ONLY`)**: Sockets authenticate via JWT and verify tenant access, but there is currently no active per-user or per-organization concurrent connection ceiling.
3. **WebSocket Ticket Handshake (`MVP ONLY`)**: WebSockets authenticate using a JWT passed via the URL query parameter (`?token=`) rather than an ephemeral single-use 30-second ticket exchange (`POST /auth/ws-ticket`).
4. **CI Pipeline Status (`CONFIG READY`)**: `.github/workflows/ci.yml` is fully specified and validated locally across all linters, types, tests, and frontend builds; pending first remote PR trigger on GitHub.
5. **Disaster Recovery (`KNOWN RISK`)**: Persistent database volumes and MinIO storage paths are separated, but automated point-in-time recovery (PITR) and multi-region replication require managed cloud infrastructure provisioning (e.g. AWS RDS Multi-AZ).
6. **Live Groq LLM Provider (`FULLY VERIFIED LIVE`)**: Grounded contract Q&A using Groq Cloud's `llama-3.3-70b-versatile` over HTTPS with server-side citation validation, prompt injection defense, and offline deterministic fallback is fully implemented and verified live against active cloud endpoints with zero client-side credential exposure.
