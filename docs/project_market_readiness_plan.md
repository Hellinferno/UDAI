# AIBAA Market-Readiness Implementation Plan

This plan transforms the current prototype into a production-ready enterprise agent platform, addressing the critical security, operational, and financial robustness gaps.

## Phase 1: Intake, Security, and Core Persistence
**Goal:** Transition from an in-memory, single-tenant prototype to a secure, durable, multi-tenant system.

- **Tasks:**
  - **Database Migration:** Replace `MemoryStore` in `store.py` with SQLAlchemy + PostgreSQL. Add a structured schema for Deals, Documents, Runs, and Audits.
  - **Tenant Isolation:** Add `tenant_id` and `owner_id` to the `Deal` model and apply row-level security or strict WHERE clauses to all reads/writes.
  - **Auth & Middleware:** Implement JWT-based auth middleware (e.g., using FastAPI `Depends`), attach user context to Requests, and enforce `Authorization` via proper IAM scopes (RBAC).
  - **Storage Abstraction:** Move document uploads from local `data/uploads` to Azure Blob Storage / AWS S3. 
- **File-Level Changes:** 
  - `apps/api/src/store.py` -> Remove/refactor to DB sessions.
  - `apps/api/src/models.py` -> Map Pydantic models to ORM models.
  - `apps/api/src/routers/*.py` -> Inject DB session and Auth dependency.

## Phase 2: Ingestion & Asynchronous Execution
**Goal:** Decouple agent processing from HTTP boundaries and ensure safe, resilient document handling.

- **Tasks:**
  - **Asynchronous Run Engine:** Move `orchestrator.run()` to a background worker (e.g., Celery, Redis Queue, or Temporal) so the API immediately returns `202 Accepted` with a job ID.
  - **Status Polling:** Update the Frontend (`AgentsTab.tsx`) to poll for task progression, removing the risk of browser timeouts on long computations.
  - **Document Gating:** Restrict downstream models from accessing partially parsed data. Add malware scanning and parse failure queues.
  - **Strict Determinism:** Eliminate "silent" fallbacks when LLM quota is hit. Restrict the agent to hard-fail with clear human-readable logging. *(Initial safety patch applied)*.
- **File-Level Changes:**
  - `apps/api/src/routers/agents.py` -> Dispatch to Celery task instead of blocking.
  - `apps/web/src/components/workspace/AgentsTab.tsx` -> Switch from `await runAgent(...)` to asynchronous polling.
  - `apps/api/src/engine/llm.py` -> Enforce strict exception handling. *(Completed)*

## Phase 3: Valuation Intelligence, Governance & Operations
**Goal:** Establish real-time financial accuracy, rigorous verifiable outputs, and observability.

- **Tasks:**
  - **Live Market Data:** Integrate AlphaVantage, Yahoo Finance, or similar APIs to fetch live market-cap, share price, and peer multi-factor benchmarks instead of static `comps.py` assumptions.
  - **Critic / Review Agent Loop:** Introduce an asynchronous "Review Agent" that critiques the draft outputs against real-time peer groups before presenting to user.
  - **Governance Workflow:** Introduce a "Draft" vs "Published" workflow for outputs. Implement approval state machines, preventing output downloads until an authorized Role validates the DCF.
  - **Telemetry & Tracing:** Add OpenTelemetry/structured logging across the FastAPI boundary and Worker boundaries to track prompt inputs, token usage, and latency. 
- **File-Level Changes:**
  - `apps/api/src/engine/comps.py` -> Replace local stubs with active REST API integrations.
  - `apps/api/src/agents/modeling.py` -> Extract "Critic" logic into a separate step.
  - `apps/api/src/routers/outputs.py` -> Implement RBAC governance checks on resource retrieval.

---
*Note: As an immediate first step in the current codebase, silent generic fallbacks have been restricted (falling back now raises explicit framework errors) and the agent runner has been gated strictly behind `parse_status` readiness.*
