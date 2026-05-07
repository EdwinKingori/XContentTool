# X-Content Automation Tool — System Architecture

> **Version:** 1.0.0 | **Status:** Active Development | **Last Updated:** 2026-05-07
> **Author:** Edwin King'ori

---

## Table of Contents

1. [What This System Does ](#1-what-this-system-does)
2. [Who This Is For](#2-who-this-is-for)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Component Deep-Dive](#5-component-deep-dive)
6. [Multi-Tenancy Model](#6-multi-tenancy-model)
7. [Data Flow Walkthroughs](#7-data-flow-walkthroughs)
8. [Database Schema Overview](#8-database-schema-overview)
9. [Async Job Pipeline](#9-async-job-pipeline)
10. [Security Architecture](#10-security-architecture)
11. [Development Phases & GitHub Branches](#11-development-phases--github-branches)
12. [CI/CD Pipeline](#12-cicd-pipeline)
13. [Infrastructure & Docker Layout](#13-infrastructure--docker-layout)
14. [Scalability Considerations](#14-scalability-considerations)
15. [Glossary](#15-glossary)

---

## 1. What This System Does

Think of this platform as a smart social media assistant that lives in the cloud. You upload a spreadsheet (Excel workbook) containing tweets you want to post — with the text, the date, and the time — and the system takes over from there. It reads your spreadsheet, understands the schedule, and posts each tweet to X (formerly Twitter) at exactly the right moment, automatically, without you lifting a finger.

You can manage multiple X accounts, multiple teams, and thousands of posts — all from one place.

**The core loop, simplified:**

```
You upload an Excel file  →  System reads & stores the posts
       ↓
You set a schedule  →  System queues jobs in the background
       ↓
Time arrives  →  System publishes tweet to X automatically
       ↓
You see results on your dashboard
```

---

## 2. Who This Is For

| Persona | Pain Point Solved |
|---|---|
| Solo content creator | No more manual copy-paste scheduling |
| Marketing agency | Manage multiple client X accounts from one dashboard |
| Brand team | Plan a month of content in a spreadsheet, fire and forget |
| Developer / SaaS operator | Multi-tenant infrastructure, white-label ready |

---

## 3. High-Level Architecture

```
                    ┌──────────────────────────────────┐
                    │          React SPA (Phase 7)     │
                    │  Dashboard · Scheduler · Uploads │
                    └──────────────────┬───────────────┘
                                       │  HTTPS / REST + WebSocket
                                       ▼
                    ┌──────────────────────────────────┐
                    │          FastAPI Gateway          │
                    │  Auth · Routing · Validation      │
                    │  /api/v1/*                        │
                    └──────┬───────────────┬────────────┘
                           │               │
           ┌───────────────┘               └──────────────────┐
           ▼                                                   ▼
┌──────────────────┐                             ┌────────────────────┐
│  PostgreSQL DB   │                             │   Redis Broker     │
│  Multi-tenant    │                             │   Task Queue       │
│  SaaS metadata  │                             │   Cache Layer      │
│  Posts, Users,   │                             └────────┬───────────┘
│  Workbooks       │                                      │
└──────────────────┘                                      ▼
                                              ┌────────────────────┐
                                              │   Celery Workers   │
                                              │   parse_workbook   │
                                              │   schedule_post    │
                                              │   publish_post     │
                                              └────────┬───────────┘
                                                       │
                                    ┌──────────────────┼───────────────────┐
                                    ▼                  ▼                   ▼
                           ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
                           │  X API v2    │  │  File Store  │  │  Celery Beat     │
                           │  Publisher   │  │  Excel .xlsx │  │  Cron Scheduler  │
                           │  OAuth 2.0   │  │  S3 / Local  │  │  (time-triggers) │
                           └──────────────┘  └──────────────┘  └──────────────────┘
```

---

## 4. Technology Stack

### Why each technology was chosen

| Layer | Technology | What it does | Why we chose it |
|---|---|---|---|
| API Framework | **FastAPI** | Handles all HTTP requests, routing, validation | Async-first, auto-generates OpenAPI docs, fastest Python framework |
| Database | **PostgreSQL** | Stores all persistent data (users, posts, tenants) | ACID-compliant, excellent JSON support, scales to millions of rows |
| Task Queue Broker | **Redis** | Message bus between FastAPI and Celery workers | Sub-millisecond latency, built-in pub/sub, industry-standard broker |
| Background Workers | **Celery** | Executes async jobs (parsing, scheduling, publishing) | Battle-tested distributed task queue with retry + scheduling built in |
| Scheduler | **Celery Beat** | Triggers time-based publishing jobs | Runs as a sidecar service, reads the DB for pending schedules |
| File Parsing | **openpyxl / pandas** | Reads and validates Excel workbooks | openpyxl is pure-Python .xlsx reader; pandas for transformation |
| File Storage | **Local / S3-compatible** | Stores uploaded Excel files | Swappable: local for dev, MinIO or AWS S3 for production |
| Containerization | **Docker + Docker Compose** | Packages every service into isolated containers | Reproducible environments, one command to run the full stack |
| CI/CD | **GitHub Actions** | Automated testing, linting, deployment on every push | Native GitHub integration, free tier generous for OSS |
| Frontend | **React + TypeScript + Vite** | Browser-based user interface | Component model maps well to multi-tenant dashboards; Vite = fast DX |
| X Integration | **X API v2** | OAuth 2.0 + tweet publishing | Official API, supports media upload, rate limit headers |
| Observability | **Sentry + Prometheus + Flower** | Error tracking, metrics, Celery dashboard | Full visibility into failures and queue health |
| ORM | **SQLAlchemy 2.x (async)** | Pythonic database access layer | Async sessions pair naturally with FastAPI; Alembic for migrations |

---

## 5. Component Deep-Dive

### 5.1 FastAPI Gateway

The API gateway is the **single entry point** for all client interactions. It is responsible for:

- **Request validation** via Pydantic v2 models (schema enforcement at the boundary)
- **JWT authentication** — every protected route requires a `Bearer` token
- **Tenant resolution** — middleware extracts the tenant context from the JWT and scopes every DB query accordingly
- **Rate limiting** — per-tenant request throttling via Redis sliding window counters
- **Background task dispatch** — enqueues Celery tasks without blocking the HTTP response

**Key routers:**

```
/api/v1/auth/         → Register, login, refresh, X OAuth callback
/api/v1/workbooks/    → Upload, list, parse, delete Excel files
/api/v1/posts/        → CRUD for scheduled posts
/api/v1/schedules/    → Publishing schedule management
/api/v1/accounts/     → X account linking per tenant
/api/v1/analytics/    → Post metrics and engagement data
/api/v1/admin/        → Tenant management (superadmin only)
```

### 5.2 PostgreSQL — Data Layer

PostgreSQL is the source of truth. All business state lives here. SQLAlchemy's async engine (`asyncpg` driver) handles connection pooling and non-blocking I/O.

Alembic manages all schema migrations — no direct DDL changes allowed outside of migration files.

### 5.3 Redis — Broker + Cache

Redis wears two hats:

1. **Message broker** — Celery serializes task payloads as JSON and pushes them into Redis queues. Workers pop tasks and execute them independently.
2. **Cache** — Stores rate limit counters, JWT revocation lists (for logout), and short-lived session metadata.

### 5.4 Celery Workers

Workers are stateless Python processes that consume tasks from Redis queues. Each worker type runs in its own Docker container for isolation and independent scaling.

**Task types:**

| Task | Trigger | What it does |
|---|---|---|
| `parse_workbook` | Workbook upload | Reads Excel file, validates rows, persists post records to DB |
| `schedule_posts` | Post creation / edit | Registers posts into the Celery Beat schedule |
| `publish_post` | Beat time trigger | Calls X API to create tweet; updates post status in DB |
| `refresh_x_token` | Token expiry | Refreshes OAuth 2.0 access tokens per tenant account |
| `generate_analytics` | Periodic (hourly) | Pulls engagement metrics from X API and stores in DB |

### 5.5 Celery Beat — Scheduler

Beat is a lightweight daemon that ticks on a configurable interval, reads the schedule from the database (`DatabaseScheduler`), and fires `publish_post` tasks at the exact moment a post is due. It acts like a cloud-native cron daemon scoped to each tenant's schedule.

### 5.6 X API Publisher

An isolated service module (`app/publishers/x_publisher.py`) that wraps the X API v2 client. Responsibilities:

- OAuth 2.0 PKCE flow — acquiring and refreshing per-tenant access tokens
- Tweet creation (`POST /2/tweets`)
- Media upload for images/videos (`POST /2/media/upload`)
- Exponential backoff on 429 (rate limit) and 5xx errors
- Publishing receipts stored back into the database with tweet ID and timestamp

### 5.7 File Storage

| Environment | Backend | Configuration |
|---|---|---|
| Local development | Docker volume / local filesystem | `STORAGE_BACKEND=local` |
| Staging / Production | AWS S3 or MinIO (S3-compatible) | `STORAGE_BACKEND=s3` |

Files are stored under a tenant-namespaced path: `/{tenant_id}/workbooks/{uuid}.xlsx`

---

## 6. Multi-Tenancy Model

This platform is **multi-tenant**: multiple independent organizations (tenants) share the same infrastructure but are completely isolated from each other's data.

### Tenant Isolation Strategy: Shared Schema + Row-Level Isolation

Every database table that contains tenant data includes a `tenant_id` (UUID foreign key). SQLAlchemy middleware automatically appends `WHERE tenant_id = :current_tenant` to every query, making cross-tenant data leakage architecturally impossible at the ORM layer.

```
Tenant A (Acme Corp)          Tenant B (Brand XYZ)
  ├── users                     ├── users
  ├── workbooks                 ├── workbooks
  ├── posts                     ├── posts
  └── x_accounts                └── x_accounts
         │                              │
         └──────────────────────────────┘
                     │
              PostgreSQL (shared tables)
              tenant_id column enforces isolation
```

**Why not separate databases per tenant?** At scale this becomes operationally expensive. Row-level isolation is the industry standard for early-to-mid stage SaaS and scales to hundreds of tenants on a single Postgres instance.

### Tenant Hierarchy

```
Platform (Superadmin)
  └── Tenant (Organization)
        ├── Owner (1 per tenant)
        ├── Admin
        ├── Editor (can draft & schedule)
        └── Viewer (read-only dashboard)
```

---

## 7. Data Flow Walkthroughs

### 7.1 Uploading an Excel Workbook

```
1. User selects .xlsx file in React dashboard
2. React sends multipart POST /api/v1/workbooks/upload  (Bearer token)
3. FastAPI validates token → resolves tenant_id
4. FastAPI streams file to File Storage, saves metadata to PostgreSQL
5. FastAPI enqueues `parse_workbook(workbook_id)` task to Redis
6. FastAPI responds 202 Accepted + workbook_id (non-blocking)
7. Celery worker picks up task from Redis queue
8. Worker: opens xlsx, validates headers, iterates rows
9. Worker: for each valid row → INSERT into posts table (status=PENDING)
10. Worker: marks workbook.status = PARSED in DB
11. React dashboard polls /api/v1/workbooks/{id} → shows PARSED + post count
```

### 7.2 Publishing a Scheduled Post

```
1. Celery Beat checks DB every 30 seconds for posts where:
   scheduled_at <= NOW() AND status = PENDING AND tenant.active = TRUE
2. Beat dispatches `publish_post(post_id)` task to Redis
3. Worker picks task, fetches post + x_account credentials from DB
4. Worker: calls X API POST /2/tweets with post content
5. X API responds 201 with tweet_id
6. Worker: UPDATE posts SET status=PUBLISHED, tweet_id=..., published_at=NOW()
7. Worker: enqueues `generate_analytics(tweet_id)` for later metric collection
```

### 7.3 X OAuth 2.0 Account Linking

```
1. User clicks "Connect X Account" in dashboard
2. React calls GET /api/v1/accounts/x/authorize
3. FastAPI generates OAuth 2.0 PKCE code_verifier + code_challenge
4. FastAPI stores code_verifier in Redis (TTL 10 min), keyed to state param
5. FastAPI redirects browser to X OAuth consent screen
6. User grants permission → X redirects to /api/v1/accounts/x/callback?code=...
7. FastAPI retrieves code_verifier from Redis, exchanges code for access_token
8. FastAPI encrypts tokens (Fernet) and stores in x_accounts table
9. Account is now linked; future publish tasks use this tenant's credentials
```

---

## 8. Database Schema Overview

```
tenants
  id (UUID PK)
  name, slug, plan_tier
  is_active, created_at

users
  id (UUID PK)
  tenant_id (FK → tenants)
  email, hashed_password, role
  is_active, created_at

x_accounts
  id (UUID PK)
  tenant_id (FK → tenants)
  x_user_id, x_handle
  encrypted_access_token, encrypted_refresh_token
  token_expires_at, created_at

workbooks
  id (UUID PK)
  tenant_id (FK → tenants)
  uploaded_by (FK → users)
  filename, storage_path
  status (UPLOADING | PARSING | PARSED | FAILED)
  row_count, created_at

posts
  id (UUID PK)
  tenant_id (FK → tenants)
  workbook_id (FK → workbooks)
  x_account_id (FK → x_accounts)
  content (TEXT)
  media_urls (JSONB)
  scheduled_at (TIMESTAMPTZ)
  status (PENDING | QUEUED | PUBLISHED | FAILED | CANCELLED)
  tweet_id, published_at
  retry_count, last_error

post_analytics
  id (UUID PK)
  post_id (FK → posts)
  impressions, likes, retweets, replies, link_clicks
  collected_at

celery_tasks (audit log)
  id (UUID PK)
  task_id, task_name
  tenant_id, related_entity_id
  status, started_at, completed_at, error
```

---

## 9. Async Job Pipeline

### Queue Architecture

```
Redis Broker
  ├── Queue: default          → general tasks
  ├── Queue: parsing          → parse_workbook (CPU-bound, isolated)
  ├── Queue: publishing       → publish_post (network I/O, high priority)
  └── Queue: analytics        → generate_analytics (low priority)
```

Separating queues means a surge in file uploads (parsing queue) never starves the publishing queue. Workers are pinned to specific queues per container.

### Task Retry Policy

| Task | Max Retries | Backoff Strategy | Dead Letter |
|---|---|---|---|
| `parse_workbook` | 3 | 60s, 120s, 300s | Mark workbook FAILED |
| `publish_post` | 5 | Exponential (30s base) | Mark post FAILED, notify user |
| `refresh_x_token` | 3 | 60s fixed | Deactivate account, notify |
| `generate_analytics` | 2 | 300s fixed | Skip silently, retry next cycle |

### Celery Flower (Monitoring)

Flower is a real-time Celery monitoring dashboard exposed at `http://localhost:5555` in development. It shows:
- Active / reserved / scheduled tasks per queue
- Worker availability and task throughput
- Per-task execution history and failure traces

---

## 10. Security Architecture

| Concern | Implementation |
|---|---|
| Authentication | JWT (HS256) with 15-min access tokens + 7-day refresh tokens |
| Authorization | Role-Based Access Control (RBAC) via FastAPI dependency injection |
| Tenant isolation | `tenant_id` enforced at ORM layer on every query |
| OAuth token storage | Encrypted at rest using Fernet symmetric encryption (key from env) |
| File upload | MIME type validation, max file size limit, virus scan hook (Phase 6) |
| Rate limiting | Redis sliding window per tenant per endpoint |
| Secrets management | `.env` files in dev; environment injection in CI/CD; secrets manager in prod |
| CORS | Strict origin allowlist via FastAPI CORS middleware |
| HTTPS | Nginx reverse proxy with TLS termination (Certbot / AWS ACM in prod) |
| Dependency scanning | `pip-audit` runs in CI on every PR |

---

## 11. Development Phases & GitHub Branches

Each phase is a long-lived feature branch that gets PR'd into `main` after review and CI passes.

```
main                    (always deployable)
  ├── phase/1-foundation
  ├── phase/2-auth-multitenancy
  ├── phase/3-workbook-management
  ├── phase/4-celery-scheduling
  ├── phase/5-x-api-publisher
  ├── phase/6-analytics-monitoring
  ├── phase/7-react-frontend
  └── phase/8-production-hardening
```

---

### Phase 1 — Foundation & Infrastructure
**Branch:** `phase/1-foundation`

**Goal:** Every developer can run the full stack locally with one command.

| Task | Details |
|---|---|
| Docker & Docker Compose | Services: `api`, `db`, `redis`, `worker`, `beat`, `flower` |
| FastAPI skeleton | Health check, root endpoint, lifespan handler |
| PostgreSQL + SQLAlchemy | Async engine (`asyncpg`), base model, connection pool |
| Alembic | Migration framework initialized, first empty migration |
| Environment config | `pydantic-settings` for `.env` validation |
| GitHub Actions CI | Lint (`ruff`), type-check (`mypy`), unit tests (`pytest`) |
| `.gitignore` + `Makefile` | Developer ergonomics |

**Deliverable:** `docker compose up` boots the stack; `/api/v1/health` returns 200 with DB + Redis connectivity status.

---

### Phase 2 — Multi-Tenant Auth & User Management
**Branch:** `phase/2-auth-multitenancy`

**Goal:** Secure, tenant-isolated user authentication and account management.

| Task | Details |
|---|---|
| Tenant model + migration | `tenants` table, slug-based lookup |
| User model + migration | `users` table with bcrypt password hashing |
| JWT auth | `python-jose` — access + refresh token pair |
| Auth router | `POST /register`, `POST /login`, `POST /refresh`, `POST /logout` |
| Tenant middleware | Extracts `tenant_id` from JWT, scopes all downstream DB sessions |
| RBAC decorators | `require_role(Role.ADMIN)` FastAPI dependency |
| Token revocation | Redis-backed JWT blocklist (on logout) |
| Tests | Pytest + `httpx.AsyncClient` — auth flows, tenant isolation assertions |

**Deliverable:** Users can register, log in, and make authenticated requests. A User from Tenant A cannot access Tenant B's data.

---

### Phase 3 — Excel Workbook Management
**Branch:** `phase/3-workbook-management`

**Goal:** Users can upload Excel files; the system parses them and stores post records.

| Task | Details |
|---|---|
| File upload endpoint | `POST /api/v1/workbooks/upload` — multipart, MIME validation |
| File storage service | Abstracted `StorageBackend` — local (dev) / S3 (prod) |
| Workbook model + migration | `workbooks` table, status state machine |
| Excel parser worker | `parse_workbook` Celery task — openpyxl row iteration, validation |
| Post model + migration | `posts` table with all scheduling fields |
| Row validation rules | Required columns: `content`, `scheduled_at`, `x_account_id` |
| Error reporting | Invalid rows stored as `parse_errors` JSON on workbook record |
| Workbook CRUD API | List, get, delete endpoints |
| Tests | Upload + parse pipeline integration test with real `.xlsx` fixture |

**Deliverable:** Upload an Excel file → API responds 202 → Celery parses it → posts appear in the database with `PENDING` status.

---

### Phase 4 — Celery Async Workers & Scheduling
**Branch:** `phase/4-celery-scheduling`

**Goal:** The background job engine is production-ready with monitoring, retries, and multi-queue routing.

| Task | Details |
|---|---|
| Celery app factory | Queue routing, serializer config (JSON), result backend |
| Beat + `DatabaseScheduler` | `django-celery-beat`-style DB-driven schedule for posts |
| `schedule_post` task | Registers/updates Beat entries when post is created/updated |
| Multi-queue routing | `parsing`, `publishing`, `analytics` queues with dedicated workers |
| Retry policies | Per-task `autoretry_for`, `max_retries`, `countdown` config |
| Dead-letter handling | On max retries: update post/workbook status, log error |
| Flower integration | Configured in `docker-compose.yml`, auth-protected |
| Health check endpoint | `/api/v1/health` expanded to report worker + beat status via Redis ping |
| Tests | Mock Celery in unit tests; real broker in integration tests |

**Deliverable:** A post with `scheduled_at = NOW() + 2 minutes` is automatically dispatched and executed by a Celery worker with full retry safety.

---

### Phase 5 — X API Publisher
**Branch:** `phase/5-x-api-publisher`

**Goal:** The system can connect X accounts and publish tweets automatically.

| Task | Details |
|---|---|
| X OAuth 2.0 PKCE flow | `/authorize` + `/callback` endpoints, `code_verifier` in Redis |
| Token encryption | Fernet encryption for `access_token` / `refresh_token` at rest |
| `x_accounts` model | Migration, CRUD API |
| X API client wrapper | `tweepy` or `httpx`-based client, rate limit awareness |
| `publish_post` task | Full publishing pipeline: fetch post → call X API → update DB |
| `refresh_x_token` task | Scheduled token refresh before expiry |
| Media upload | Image/video attachment support (`POST /2/media/upload`) |
| Error taxonomy | Map X API error codes to post failure reasons |
| Tests | VCR cassettes (recorded HTTP interactions) for X API calls |

**Deliverable:** Link an X account via OAuth → upload a workbook with a post scheduled 5 minutes out → tweet appears on X automatically.

---

### Phase 6 — Analytics & Observability
**Branch:** `phase/6-analytics-monitoring`

**Goal:** Full operational visibility into the system and basic engagement analytics.

| Task | Details |
|---|---|
| `generate_analytics` task | Polls X API for tweet metrics, stores in `post_analytics` |
| Analytics API | `GET /api/v1/analytics/posts` — impressions, likes, retweets per post |
| Sentry integration | Exception capture with tenant context tagging |
| Prometheus metrics | Custom metrics: tasks enqueued, published, failed; latency histograms |
| Grafana dashboard | Pre-built dashboard JSON for import |
| Structured logging | `structlog` — JSON logs with `tenant_id`, `task_id`, `post_id` |
| Audit log | `celery_tasks` table records every task lifecycle event |

**Deliverable:** Operations team can see system health in Grafana; errors surface in Sentry with full context.

---

### Phase 7 — React Frontend SPA
**Branch:** `phase/7-react-frontend`

**Goal:** A polished, intuitive dashboard for all platform capabilities.

| Task | Details |
|---|---|
| Vite + React + TypeScript | Project scaffold under `frontend/` |
| React Query | Server state management for API calls + background polling |
| Auth flows | Login, register, JWT token storage (httpOnly cookie strategy) |
| Workbook management UI | Drag-and-drop upload, parse status, post preview table |
| Post scheduler | Calendar view + list view, status badges, manual override |
| X account management | OAuth connect button, connected accounts list |
| Analytics dashboard | Charts (Recharts/Chart.js) — impressions, likes over time |
| Real-time updates | WebSocket connection for live job status |
| Tenant admin panel | User invite, role management, subscription info |
| Docker integration | `frontend` service in `docker-compose.yml`, Nginx serving |

**Deliverable:** End-to-end user journey completable in the browser — from signup to tweet published.

---

### Phase 8 — Production Hardening & Scaling
**Branch:** `phase/8-production-hardening`

**Goal:** The system is ready for real-world traffic, security audits, and commercial launch.

| Task | Details |
|---|---|
| Horizontal worker scaling | `docker compose scale worker=5` or Kubernetes HPA |
| S3 production storage | AWS S3 or Cloudflare R2 for workbook files |
| Nginx reverse proxy | TLS termination, gzip, static asset serving |
| Load testing | `locust` scenarios for upload + publish pipelines |
| Dependency audit | `pip-audit`, SAST scan |
| GDPR compliance hooks | Data export + deletion endpoints per tenant |
| Backup strategy | Automated PostgreSQL WAL archiving to S3 |
| API versioning strategy | `/api/v2/` namespace planning |
| Runbook documentation | On-call procedures for common failure modes |

**Deliverable:** Platform survives a load test of 100 concurrent tenants, each with 1,000 scheduled posts.

---

## 12. CI/CD Pipeline

```
Developer pushes to feature branch
           │
           ▼
    GitHub Actions: PR Checks
    ├── ruff (lint + format)
    ├── mypy (static type check)
    ├── pytest (unit tests, no external deps)
    └── docker build (image buildable)
           │
           ▼ (PR merged to main)
    GitHub Actions: Integration Tests
    ├── docker compose up (full stack)
    ├── pytest --integration (real DB + Redis)
    ├── pip-audit (dependency vulnerability scan)
    └── Build & push Docker image to registry
           │
           ▼ (tagged release)
    GitHub Actions: Deploy
    ├── SSH into staging server
    ├── docker compose pull + up -d
    └── Smoke test: /api/v1/health == 200
```

### GitHub Actions Workflow Files

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | Every push / PR | Lint, type-check, unit tests |
| `.github/workflows/integration.yml` | Merge to main | Full stack integration tests |
| `.github/workflows/deploy-staging.yml` | Merge to main | Deploy to staging environment |
| `.github/workflows/deploy-prod.yml` | Tagged release `v*.*.*` | Deploy to production |

---

## 13. Infrastructure & Docker Layout

### `docker-compose.yml` Services

| Service | Image | Role | Ports |
|---|---|---|---|
| `api` | `./Dockerfile` (FastAPI) | REST API gateway | `8000:8000` |
| `db` | `postgres:16-alpine` | PostgreSQL database | `5432` (internal) |
| `redis` | `redis:7-alpine` | Message broker + cache | `6379` (internal) |
| `worker-parsing` | `./Dockerfile` (Celery) | Parses Excel workbooks | — |
| `worker-publishing` | `./Dockerfile` (Celery) | Publishes tweets to X | — |
| `beat` | `./Dockerfile` (Celery Beat) | Fires scheduled tasks | — |
| `flower` | `mher/flower` | Celery monitoring UI | `5555:5555` |
| `frontend` | `./frontend/Dockerfile` | React SPA (Nginx) | `3000:80` |

### Project Directory Structure

> Legend: `[exists]` — file already present | `[planned]` — to be added in the indicated phase

```
X-Content-Automation-Tool/
│
├── app/                                         [exists]
│   │
│   ├── api/                                     [exists]
│   │   ├── dependencies/                        [exists — empty]
│   │   │   ├── __init__.py                      [planned — Phase 2]
│   │   │   ├── auth.py                          [planned — Phase 2]  JWT validation, current_user dep
│   │   │   ├── tenant.py                        [planned — Phase 2]  tenant_id resolver, DB session scoping
│   │   │   └── pagination.py                    [planned — Phase 2]  shared query-param deps (page, limit)
│   │   │
│   │   └── v1/                                  [exists — empty]
│   │       ├── __init__.py                      [planned — Phase 2]
│   │       ├── router.py                        [planned — Phase 2]  aggregated v1 APIRouter
│   │       ├── auth.py                          [planned — Phase 2]  /register, /login, /refresh, /logout
│   │       ├── workbooks.py                     [planned — Phase 3]  upload, list, get, delete workbooks
│   │       ├── posts.py                         [planned — Phase 3]  CRUD for scheduled posts
│   │       ├── accounts.py                      [planned — Phase 5]  X OAuth account linking
│   │       ├── analytics.py                     [planned — Phase 6]  engagement metrics endpoints
│   │       └── health.py                        [planned — Phase 1]  /health with DB + Redis status
│   │
│   ├── core/                                    [exists]
│   │   ├── config.py                            [exists]             pydantic-settings env validation
│   │   └── logging/                             [exists]
│   │       ├── context.py                       [exists]             structlog context vars (tenant_id etc.)
│   │       ├── logs.py                          [exists]             logger factory, JSON formatter
│   │       ├── middleware.py                    [exists]             request/response logging middleware
│   │       └── route_logger.py                  [exists]             per-route access log handler
│   │
│   ├── db/                                      [exists]
│   │   ├── database.py                          [exists]             async SQLAlchemy engine + base model
│   │   └── session.py                           [exists]             AsyncSession factory, get_db dep
│   │
│   ├── docs/                                    [exists]
│   │   └── system_architecture.md               [exists]             this document
│   │
│   ├── models/                                  [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 2]
│   │   ├── base.py                              [planned — Phase 1]  declarative base, UUID PK + timestamp mixin
│   │   ├── tenant.py                            [planned — Phase 2]  Tenant ORM model
│   │   ├── user.py                              [planned — Phase 2]  User ORM model with RBAC role field
│   │   ├── x_account.py                         [planned — Phase 5]  X OAuth credentials per tenant
│   │   ├── workbook.py                          [planned — Phase 3]  Workbook ORM model + status enum
│   │   ├── post.py                              [planned — Phase 3]  Post ORM model + status state machine
│   │   └── analytics.py                         [planned — Phase 6]  PostAnalytics ORM model
│   │
│   ├── redis/                                   [exists]
│   │   ├── redis_config.py                      [exists]             Redis client factory, connection pool
│   │   └── hmac_security.py                     [exists]             HMAC signing for sensitive Redis keys
│   │
│   ├── repositories/                            [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 2]
│   │   ├── base.py                              [planned — Phase 2]  generic async CRUD repository
│   │   ├── tenant_repository.py                 [planned — Phase 2]  tenant lookup + provisioning
│   │   ├── user_repository.py                   [planned — Phase 2]  user creation, login lookup
│   │   ├── workbook_repository.py               [planned — Phase 3]  workbook CRUD + status updates
│   │   └── post_repository.py                   [planned — Phase 3]  post CRUD, pending-post queries
│   │
│   ├── schemas/                                 [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 2]
│   │   ├── common.py                            [planned — Phase 2]  PaginatedResponse, ErrorResponse, UUIDSchema
│   │   ├── auth.py                              [planned — Phase 2]  LoginRequest, TokenResponse, RegisterRequest
│   │   ├── tenant.py                            [planned — Phase 2]  TenantCreate, TenantRead
│   │   ├── user.py                              [planned — Phase 2]  UserCreate, UserRead, UserUpdate
│   │   ├── workbook.py                          [planned — Phase 3]  WorkbookRead, WorkbookUploadResponse
│   │   ├── post.py                              [planned — Phase 3]  PostCreate, PostRead, PostStatusUpdate
│   │   └── analytics.py                         [planned — Phase 6]  AnalyticsRead, EngagementSummary
│   │
│   ├── security/                                [exists]
│   │   ├── jwt.py                               [exists]             JWT encode/decode, token pair generation
│   │   ├── password.py                          [exists]             bcrypt hashing + verification
│   │   ├── api_keys.py                          [exists]             API key generation + validation
│   │   └── rate_limiter.py                      [exists]             Redis sliding-window rate limiter
│   │
│   ├── services/                                [exists]
│   │   ├── __init__.py                          [exists]
│   │   ├── pagination.py                        [exists]             offset/cursor pagination helpers
│   │   ├── sorting.py                           [exists]             dynamic sort-field validation
│   │   └── helpers/                             [exists]
│   │       ├── __init__.py                      [exists]
│   │       ├── crud_helper.py                   [exists]             reusable create/update/delete patterns
│   │       └── redis_helpers.py                 [exists]             typed Redis get/set/delete wrappers
│   │
│   ├── sql/                                     [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 3]
│   │   ├── scheduling_queries.py                [planned — Phase 4]  raw SQL for pending-post Beat polling
│   │   └── analytics_queries.py                 [planned — Phase 6]  heavy aggregation queries
│   │
│   ├── tasks/                                   [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 4]
│   │   ├── celery_app.py                        [planned — Phase 4]  Celery app factory, queue routing config
│   │   ├── parse_workbook.py                    [planned — Phase 3]  openpyxl row iteration + DB insertion
│   │   ├── publish_post.py                      [planned — Phase 5]  X API tweet creation + status update
│   │   ├── refresh_token.py                     [planned — Phase 5]  OAuth 2.0 token refresh for X accounts
│   │   └── analytics.py                         [planned — Phase 6]  tweet metric collection from X API
│   │
│   ├── templates/                               [exists — empty]
│   │   ├── email/                               [planned — Phase 5]
│   │   │   ├── welcome.html                     [planned — Phase 2]  new user onboarding email
│   │   │   └── publish_failure.html             [planned — Phase 5]  post failure notification email
│   │   └── oauth_callback.html                  [planned — Phase 5]  browser landing page after X OAuth
│   │
│   ├── utils/                                   [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 1]
│   │   ├── datetime_utils.py                    [planned — Phase 3]  timezone-aware parse + formatting helpers
│   │   ├── file_utils.py                        [planned — Phase 3]  MIME detection, extension validation
│   │   └── encryption.py                        [planned — Phase 5]  Fernet encrypt/decrypt for OAuth tokens
│   │
│   ├── workers/                                 [exists — empty]
│   │   ├── __init__.py                          [planned — Phase 4]
│   │   ├── config.py                            [planned — Phase 4]  concurrency, prefetch, queue-pin settings
│   │   ├── parsing_worker.py                    [planned — Phase 4]  entry point for parsing queue workers
│   │   └── publishing_worker.py                 [planned — Phase 4]  entry point for publishing queue workers
│   │
│   ├── __init__.py                              [exists]
│   └── main.py                                  [exists]             FastAPI app factory, lifespan, router mount
│
├── migrations/                                  [planned — Phase 1]  Alembic migration directory
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
│
├── tests/                                       [planned — Phase 1]
│   ├── conftest.py                              [planned — Phase 1]  pytest fixtures: test DB, async client
│   ├── unit/                                    [planned — Phase 2]
│   │   ├── test_security.py
│   │   └── test_services.py
│   ├── integration/                             [planned — Phase 2]
│   │   ├── test_auth.py
│   │   ├── test_workbooks.py
│   │   └── test_publish_pipeline.py
│   └── fixtures/
│       └── sample_workbook.xlsx                 [planned — Phase 3]  test Excel file with valid + invalid rows
│
├── frontend/                                    [planned — Phase 7]  React + TypeScript + Vite SPA
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/                                 axios client + React Query hooks
│   │   └── main.tsx
│   ├── Dockerfile
│   └── vite.config.ts
│
├── .github/                                     [planned — Phase 1]
│   └── workflows/
│       ├── ci.yml                               lint + type-check + unit tests on every PR
│       ├── integration.yml                      full stack tests on merge to main
│       ├── deploy-staging.yml                   auto-deploy to staging on merge to main
│       └── deploy-prod.yml                      deploy to production on tagged release v*.*.*
│
├── docker-compose.yml                           [planned — Phase 1]  all services: api, db, redis, workers, beat, flower
├── Dockerfile                                   [planned — Phase 1]  multi-stage build for api + worker image
├── Makefile                                     [planned — Phase 1]  dev shortcuts: make up, make migrate, make test
├── .gitignore                                   [exists]
├── README.md                                    [exists]
└── requirements.txt                             [exists]
```

---

## 14. Scalability Considerations

| Bottleneck | Strategy |
|---|---|
| High upload volume | Presigned S3 URLs for direct browser → S3 uploads (bypass API) |
| Tweet publishing rate limits | Per-account rate limit tracking in Redis; inter-task delays |
| Database connection exhaustion | PgBouncer connection pooler in front of PostgreSQL |
| Worker throughput | Horizontal scaling — add more `worker-publishing` containers |
| Beat single point of failure | Beat with DB-backed lock (only one Beat fires at a time, even with replicas) |
| Excel parsing large files | Stream parsing with `openpyxl` read-only mode; chunk large workbooks |
| Multi-region | Redis Sentinel or Redis Cluster for HA; Postgres streaming replication |

---

## 15. Glossary

| Term | Plain English | Technical Definition |
|---|---|---|
| **Tenant** | A company or organization using the platform | An isolated SaaS customer entity with its own users and data |
| **Workbook** | An Excel file full of posts | `.xlsx` file uploaded by the user; parsed into individual post records |
| **Celery** | The background robot | Distributed task queue framework for async Python job execution |
| **Celery Beat** | The alarm clock | Periodic task scheduler that fires Celery tasks at configured intervals |
| **Redis** | The messaging system | In-memory data store used as message broker and cache |
| **FastAPI** | The doorman / receptionist | Python web framework handling all HTTP requests and routing |
| **OAuth 2.0** | The "Login with X" handshake | Authorization protocol allowing the platform to post on behalf of users |
| **JWT** | Your ID badge | JSON Web Token — a signed, stateless credential passed on every API request |
| **Alembic** | Database version control | Migration tool that tracks and applies database schema changes incrementally |
| **RBAC** | Permission levels | Role-Based Access Control — Owner, Admin, Editor, Viewer permissions |
| **PKCE** | A security handshake upgrade | Proof Key for Code Exchange — OAuth 2.0 extension that prevents auth code interception |
| **Fernet** | The lockbox for secrets | Symmetric authenticated encryption for storing OAuth tokens at rest |
| **Docker Compose** | The orchestra conductor | Tool that starts all services (API, DB, Redis, workers) with one command |
| **Multi-tenancy** | Sharing one system safely | Architecture where multiple customers share infrastructure but never see each other's data |

---

*This document is maintained alongside the codebase. For questions, open a GitHub issue or contact the platform team.*
