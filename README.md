# AI Contract Risk Analyzer

> **Production-style Legal-Tech SaaS for structured contract analysis, clause-level risk detection, and human-in-the-loop review.**

AI Contract Risk Analyzer is a multi-tenant backend platform designed to help startups and SMBs identify potentially risky contract clauses without relying on a generic "chat with PDF" workflow.

Instead of treating a contract as a single document for conversational Q&A, the system processes it as structured data:

```text
Contract
   ↓
Document Extraction
   ↓
Clause Segmentation
   ↓
Clause Classification
   ↓
Playbook Evaluation
   ↓
Deterministic Risk Engine
   ↓
Risk Explanation
   ↓
Human Review
   ↓
Audit Trail / Report
```

The project is designed to demonstrate production-grade backend engineering combined with practical LLM integration.

---

## Current Status

**M0 — Skeleton Complete**

Currently implemented:

* FastAPI application
* PostgreSQL infrastructure
* Redis infrastructure
* MinIO object storage
* Docker Compose development environment
* typed configuration
* health endpoint
* structured logging foundation
* Alembic migration setup
* Ruff
* MyPy
* Pytest
* CI foundation

Contract processing begins in **M1+**.

---

# Why This Project?

Most contract AI demos stop at:

```text
Upload PDF
    ↓
RAG
    ↓
Chat with document
```

This project takes a different approach.

The goal is to build a structured analysis pipeline:

```text
Raw Contract
     ↓
Structured Clauses
     ↓
Classification
     ↓
Playbook Rules
     ↓
Deterministic Risk Score
     ↓
Human Review
```

The LLM is used as an **evidence and extraction component**, not as the sole authority for determining risk.

This makes the system easier to:

* audit
* test
* explain
* evaluate
* improve
* integrate into real workflows

---

# Key Features

## Contract Processing

Planned:

* PDF upload
* DOCX upload
* scanned-document OCR
* clause segmentation
* clause classification
* asynchronous processing

## AI Analysis

Planned:

* structured LLM extraction
* clause classification
* confidence scoring
* risk-factor extraction
* playbook evaluation
* AI-generated explanations
* alternative clause suggestions
* missing-clause detection

## Risk Engine

The final risk decision is not delegated entirely to the LLM.

Conceptually:

```text
LLM Evidence
     +
Playbook Violations
     +
Contract Characteristics
     +
Severity Weights
     ↓
Deterministic Risk Engine
     ↓
Risk Score
     ↓
LOW / MEDIUM / HIGH
```

This makes risk calculations explainable and reproducible.

---

# Example Risk Analysis

A clause such as:

> Vendor's liability under this Agreement shall be unlimited...

could produce structured analysis similar to:

```json
{
  "clause_type": "limitation_of_liability",
  "risk_level": "HIGH",
  "risk_score": 92,
  "risk_factors": [
    "No aggregate liability cap",
    "Potential exposure to consequential damages"
  ],
  "recommended_action": "Review and negotiate liability cap"
}
```

The exact output depends on the implemented extraction and risk rules.

---

# Playbook Mode

Organizations will be able to define their own acceptable contract terms.

Example:

```text
Clause Type:
limitation_of_liability

Rule:
Liability cap should not exceed 12 months of fees.

Severity:
HIGH
```

The analysis pipeline can then evaluate extracted contract facts against organization-specific rules.

Rules are represented as structured data rather than arbitrary user-supplied executable code.

---

# Multi-Tenancy

The application is designed as a multi-tenant SaaS.

Example:

```text
Organization A
 ├── Users
 ├── Contracts
 ├── Clauses
 ├── Playbook Rules
 └── Audit Logs

Organization B
 ├── Users
 ├── Contracts
 ├── Clauses
 ├── Playbook Rules
 └── Audit Logs
```

Organization A must never be able to access Organization B's data.

Tenant identity is derived from authenticated user context rather than trusted client-supplied organization IDs.

The architecture uses:

* application-level tenant filtering
* PostgreSQL Row Level Security as a second isolation layer

---

# Role-Based Access Control

Three roles are planned:

| Role     | Access                                                                |
| -------- | --------------------------------------------------------------------- |
| Admin    | Organization management, users, playbook, contracts, reviews, reports |
| Reviewer | Contract analysis, clause review, approvals/rejections                |
| Viewer   | Read-only access                                                      |

Authorization is enforced server-side.

Frontend restrictions are not treated as a security boundary.

---

# Architecture

```text
                         ┌─────────────────┐
                         │     Client      │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     FastAPI     │
                         │ Auth / API /    │
                         │ Validation      │
                         └───────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
             ┌─────────────┐          ┌─────────────┐
             │ PostgreSQL  │          │ MinIO / S3  │
             │ + pgvector │          │ Documents   │
             └──────┬──────┘          └─────────────┘
                    │
                    │
                    ▼
             ┌─────────────┐
             │   Redis     │
             │ Broker /    │
             │ Pub/Sub     │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │   Celery    │
             │   Workers   │
             └──────┬──────┘
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
       OCR       LLM        Embeddings
          │         │          │
          └─────────┼──────────┘
                    ▼
             ┌─────────────┐
             │ Risk Engine │
             └─────────────┘
```

### Core architectural rule

HTTP requests never perform expensive OCR or LLM operations.

Upload requests create a processing job and return immediately.

```text
POST /contracts/upload

        ↓

contract_id
job_id
status = queued

        ↓

Celery Worker

        ↓

document processing
```

---

# Asynchronous Processing

The planned processing pipeline is:

```text
Upload
  ↓
Validate
  ↓
Store Document
  ↓
Create Contract Version
  ↓
Create Processing Job
  ↓
Celery
  ↓
Extract Text
  ↓
OCR if required
  ↓
Segment Clauses
  ↓
Classify Clauses
  ↓
Evaluate Playbook
  ↓
Calculate Risk
  ↓
Generate Embeddings
  ↓
Detect Missing Clauses
  ↓
Finalize
  ↓
Notify
```

Each stage is designed to support:

* retries
* idempotency
* structured logging
* failure recovery
* persisted processing state

---

# Technology Stack

| Layer               | Technology                        |
| ------------------- | --------------------------------- |
| Language            | Python 3.12+                      |
| API                 | FastAPI                           |
| Validation          | Pydantic v2                       |
| ORM                 | SQLAlchemy 2.x                    |
| Database            | PostgreSQL 16                     |
| Vector Search       | pgvector                          |
| Migrations          | Alembic                           |
| Task Queue          | Celery                            |
| Broker              | Redis                             |
| Object Storage      | MinIO / S3                        |
| OCR                 | Tesseract / cloud OCR abstraction |
| LLM                 | Provider abstraction              |
| Embeddings          | Provider abstraction              |
| Testing             | Pytest                            |
| Linting             | Ruff                              |
| Type Checking       | MyPy                              |
| Containers          | Docker                            |
| Local Orchestration | Docker Compose                    |

---

# Project Structure

```text
app/
├── api/
│   └── v1/
│
├── core/
│   ├── config.py
│   ├── logging.py
│   └── exceptions.py
│
├── db/
│   ├── session.py
│   └── base.py
│
├── models/
│
├── schemas/
│
├── services/
│   ├── document/
│   ├── llm/
│   ├── embeddings/
│   ├── risk/
│   ├── playbook/
│   ├── comparison/
│   ├── reporting/
│   └── notifications/
│
├── workers/
│   ├── celery_app.py
│   └── tasks/
│
├── repositories/
│
└── utils/

tests/
├── unit/
├── integration/
├── api/
└── security/

alembic/
scripts/
docs/
```

### Layering

```text
API
 ↓
Services
 ↓
Repositories
 ↓
Database
```

API controllers remain thin.

Services contain business orchestration.

Repositories handle persistence.

This separation allows core business logic such as the risk engine to be tested without requiring a live database.

---

# Database Design

Core entities include:

```text
organizations
users
contracts
contract_versions
clauses
playbook_rules
clause_embeddings
comparisons
review_actions
audit_logs
processing_jobs
notifications
```

The schema will use:

* foreign keys
* indexes
* unique constraints
* transaction boundaries
* tenant-aware queries
* PostgreSQL RLS where appropriate

Large contract files are stored in object storage rather than PostgreSQL.

---

# Security

Security is treated as a core architectural requirement because contracts can contain confidential business information.

### File Security

Planned controls:

* magic-byte validation
* MIME allowlisting
* file-size limits
* filename sanitization
* antivirus scanning abstraction
* safe object keys
* signed URLs

### Tenant Security

```text
JWT
 ↓
Authenticated User
 ↓
Organization
 ↓
Tenant-filtered Repository
 ↓
PostgreSQL RLS
```

### AI Security

Uploaded contracts are treated as **untrusted data**.

The system must defend against document-based prompt injection.

For example, contract text containing:

```text
Ignore previous instructions...
```

must never override system instructions.

LLM prompts maintain separation between:

```text
System Instructions
Organization Rules
Document Content
```

### Secrets

Secrets are provided through environment variables.

Never commit:

```text
.env
API keys
AWS credentials
JWT secrets
database passwords
```

---

# AI Reliability Strategy

The system deliberately avoids:

```text
LLM → "HIGH RISK"
```

as the complete decision process.

Instead:

```text
Contract
   ↓
LLM extraction
   ↓
Structured validated data
   ↓
Playbook rules
   ↓
Deterministic risk engine
   ↓
Final risk
```

Benefits:

* reproducibility
* explainability
* easier testing
* easier auditing
* lower dependence on model behavior

LLM responses are validated using Pydantic schemas.

Malformed responses are rejected or retried rather than silently persisted.

---

# Semantic Search

pgvector will be used for clause embeddings.

Potential queries:

```text
"Find clauses similar to this liability clause."

"Has this organization previously flagged a similar clause?"

"Show previously approved clauses similar to this one."
```

Similarity search will always apply organization-level filtering.

The system must never use another organization's clauses as retrieval context.

---

# Contract Comparison

Future versions will support:

```text
Version A
    ↓
Version B
    ↓
Clause-level diff
    ↓
Risk delta
```

Example:

```text
Liability Clause

Version A:
LOW

Version B:
HIGH

Change:
Liability cap removed.
```

---

# Human-in-the-Loop Review

AI output is not automatically treated as final.

Reviewers will be able to:

* inspect clauses
* approve findings
* reject findings
* add review decisions
* inspect explanations
* review suggested alternatives

Important actions are recorded in the audit trail.

---

# Audit Trail

Examples:

```text
CONTRACT_UPLOADED
PROCESSING_STARTED
PROCESSING_FAILED
CLAUSE_REVIEWED
CLAUSE_APPROVED
CLAUSE_REJECTED
PLAYBOOK_RULE_CREATED
PLAYBOOK_RULE_UPDATED
REPORT_GENERATED
```

Audit records provide traceability for important actions without unnecessarily storing sensitive contract contents.

---

# API Roadmap

Planned endpoints include:

```text
POST   /api/v1/contracts/upload
GET    /api/v1/contracts
GET    /api/v1/contracts/{id}
GET    /api/v1/contracts/{id}/status
GET    /api/v1/contracts/{id}/clauses

PATCH  /api/v1/clauses/{id}/review

POST   /api/v1/contracts/{id}/compare/{other_id}

POST   /api/v1/playbook-rules
GET    /api/v1/playbook-rules
PATCH  /api/v1/playbook-rules/{id}
DELETE /api/v1/playbook-rules/{id}

GET    /api/v1/contracts/{id}/report

WS     /api/v1/contracts/{id}/live-status
```

Endpoints will be added as their corresponding milestones are implemented.

---

# Milestones

| Milestone | Scope                                    | Status     |
| --------- | ---------------------------------------- | ---------- |
| M0        | Infrastructure, config, health, CI       | ✅ Complete |
| M1        | Organizations, users, JWT, RBAC, RLS     | 🔜 Next    |
| M2        | Contract upload, validation, MinIO, jobs | ⏳          |
| M3        | PDF/DOCX extraction, OCR, Celery         | ⏳          |
| M4        | Clause segmentation + LLM classification | ⏳          |
| M5        | Playbook + deterministic risk engine     | ⏳          |
| M6        | Async pipeline, retries, idempotency     | ⏳          |
| M7        | Embeddings + pgvector search             | ⏳          |
| M8        | Missing-clause detection                 | ⏳          |
| M9        | Contract version comparison              | ⏳          |
| M10       | Review workflow + audit trail            | ⏳          |
| M11       | PDF report generation                    | ⏳          |
| M12       | Security hardening                       | ⏳          |
| M13       | Observability                            | ⏳          |
| M14       | Production deployment                    | ⏳          |
| M15       | Portfolio, benchmarks, documentation     | ⏳          |

---

# Quick Start

## Prerequisites

* Docker Desktop
* Python 3.12+
* Git
* pip or uv

## Clone

```bash
git clone <repo-url>
cd ai-contract-risk-analyzer
```

## Configure

```bash
cp .env.example .env
```

Set a secure `SECRET_KEY` and other required environment variables.

## Start infrastructure

```bash
make up
```

Expected local services:

```text
PostgreSQL → localhost:5432
Redis      → localhost:6379
MinIO      → localhost:9000
MinIO UI   → localhost:9001
```

## Install Python dependencies

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run migrations

```bash
make migrate
```

## Configure object storage

```bash
make setup-storage
```

## Start API

```bash
make run
```

API:

```text
http://localhost:8000
```

Development API documentation:

```text
http://localhost:8000/docs
```

## Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "services": {
    "db": "ok",
    "redis": "ok",
    "storage": "ok"
  }
}
```

---

# Development Commands

```bash
make lint
```

Runs Ruff checks.

```bash
make typecheck
```

Runs strict MyPy checks.

```bash
make test
```

Runs the test suite with coverage.

```bash
make ci
```

Runs the complete local quality gate.

Pre-commit:

```bash
pre-commit install
```

---

# Engineering Principles

This project follows several principles:

### 1. Async for expensive work

OCR and LLM calls never block API requests.

### 2. LLMs provide evidence, not unquestioned truth

Structured extraction is validated and risk calculation is deterministic where possible.

### 3. Security is enforced server-side

Authentication and authorization are not frontend responsibilities.

### 4. Tenant isolation is mandatory

Every organization boundary is treated as a security boundary.

### 5. Failure is expected

Celery tasks are designed around retries, idempotency, and recoverable failures.

### 6. Measure before claiming

Performance improvements and resume metrics will only be reported after being measured.

### 7. No unnecessary abstraction

Architecture should solve real problems rather than demonstrate design patterns for their own sake.

---

# Architecture Decisions

Detailed ADRs are maintained in:

```text
docs/architecture.md
```

Current decisions include:

* ADR-001 — FastAPI over Django/Flask
* ADR-002 — PostgreSQL + pgvector over dedicated vector database
* ADR-003 — Celery + Redis for asynchronous processing
* ADR-004 — Deterministic risk engine with LLM as evidence provider
* ADR-005 — PostgreSQL RLS as a second tenant-isolation layer
* ADR-006 — MinIO locally and S3 in production
* ADR-007 — Structured playbook rules instead of executable user code

Architectural decisions may change as the system evolves. Changes should be documented rather than silently introduced.

---

# Testing Strategy

Testing will cover:

## Unit

* risk scoring
* playbook evaluation
* clause schemas
* segmentation
* authorization logic

## Integration

* PostgreSQL
* pgvector
* Redis/Celery
* object storage

## API

* authentication
* RBAC
* tenant isolation
* contract upload
* clause review
* playbook APIs

## Security

* cross-tenant access attempts
* unauthorized resources
* malicious file handling
* authentication failures
* prompt injection scenarios

The test suite will prioritize negative and security cases rather than only happy paths.

---

# Production Deployment

The target production architecture is designed around:

```text
                    Internet
                       |
                       v
                 Load Balancer
                       |
                       v
                 FastAPI Service
                  /          \
                 /            \
                v              v
          PostgreSQL          S3
          / pgvector
                |
                v
              Redis
                |
                v
         Celery Worker Pool
```

Potential AWS deployment:

* ECS/Fargate for API
* ECS/Fargate for Celery workers
* RDS PostgreSQL
* S3
* managed Redis
* load balancer
* centralized logging/metrics

Workers can scale independently from API instances based on processing workload.

Production deployment will be implemented in later milestones.

---

# Performance & Observability

The system is designed to measure:

* API latency
* contract processing duration
* OCR duration
* LLM latency
* LLM failures
* token usage
* Celery task duration
* task retry count
* processing success rate
* embedding latency
* similarity-search latency

These metrics can later support evidence-based optimization and legitimate resume metrics.

---

# Limitations

This system is a contract-review assistance platform.

It does not replace qualified legal counsel.

AI-generated analysis can be incorrect and requires appropriate human review.

The project intentionally prioritizes engineering architecture and explainability over claiming autonomous legal decision-making.

---

# Roadmap

The long-term roadmap is:

```text
M0
Infrastructure
   ↓
M1
Identity + Multi-tenancy
   ↓
M2
Contract Upload
   ↓
M3
Document Processing
   ↓
M4
Clause Intelligence
   ↓
M5
Risk Engine
   ↓
M6
Async Pipeline
   ↓
M7
Semantic Search
   ↓
M8
Missing Clauses
   ↓
M9
Contract Comparison
   ↓
M10
Human Review
   ↓
M11
Reports
   ↓
M12
Security Hardening
   ↓
M13
Observability
   ↓
M14
Production Deployment
   ↓
M15
Portfolio + Benchmarks
```

---

# Portfolio Goal

The final system should demonstrate practical experience with:

```text
Python
FastAPI
Async Backend Development
PostgreSQL
SQLAlchemy
Redis
Celery
Docker
Object Storage
pgvector
LLM Integration
RAG
OCR
RBAC
Multi-Tenancy
PostgreSQL RLS
Security
Testing
Observability
Production Deployment
```

The goal is not to maximize the number of technologies.

The goal is to demonstrate that the system can be **designed, implemented, tested, secured, debugged, deployed, measured, and explained** like a real backend + AI SaaS product.

---

# License

Add the project's chosen license here before public release.

---

# Disclaimer

This project is an engineering demonstration and contract-analysis prototype.

It does not constitute legal advice and should not be relied upon as a substitute for qualified legal counsel.
