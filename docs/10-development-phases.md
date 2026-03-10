# 10 — Development Phases
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

Development is organized into **5 phases** following a strict bottom-up build order. Earlier phases establish foundational infrastructure that later phases depend on. No UI work begins until the backend and agent framework are proven working.

```
Phase 0: Foundation & Environment Setup        (Days 1–5)
Phase 1: Core Backend + Colab Integration      (Days 6–16)
Phase 2: Agent Framework + First Agent         (Days 17–27)
Phase 3: Full Agent Suite + Tools              (Days 28–38)
Phase 4: Frontend + UX                         (Days 39–46)
Phase 5: Integration, Testing & Polish         (Days 47–51)
```

---

## 2. Phase 0 — Foundation & Environment Setup
**Duration:** Days 1–5  
**Goal:** All developers can run the full stack locally. Colab inference server is live.

### 2.1 Tasks

| Task | Owner | Day | Deliverable |
|---|---|---|---|
| Initialize monorepo (`aibaa/`) with directory structure | Dev | 1 | Commit: `chore: init monorepo` |
| Set up `apps/api` FastAPI skeleton | Dev | 1 | `GET /health` returns `{"status": "ok"}` |
| Set up `apps/web` Vite + React + Tailwind | Dev | 2 | App renders blank page on `localhost:3000` |
| Configure B&W design tokens in Tailwind | Dev | 2 | `design-tokens.css` committed |
| Set up Colab notebook: install Unsloth + load base model | Dev | 3 | Model loads without OOM on T4 GPU |
| Build Colab inference server (`/generate` endpoint) | Dev | 3–4 | `POST /generate` returns completion |
| Set up ngrok tunnel in Colab | Dev | 4 | Endpoint reachable from local machine |
| Configure `settings` store with `llm_endpoint_url` | Dev | 5 | Backend can ping Colab health check |
| Set up linting (Ruff for Python, ESLint for TS) | Dev | 5 | `make lint` runs clean |

### 2.2 Exit Criteria
- [ ] `curl localhost:8000/api/v1/health` → `{"status": "ok"}`
- [ ] `curl {COLAB_URL}/health` → `{"status": "healthy", "model_loaded": true}`
- [ ] React app loads at `localhost:3000` with no console errors
- [ ] A simple test prompt sent to Colab returns a text completion

---

## 3. Phase 1 — Core Backend + Data Model
**Duration:** Days 6–16  
**Goal:** All API endpoints are implemented. In-memory store is working. File upload and parsing are live.

### 3.1 Milestones

**Milestone 1.1 — Deals API (Days 6–8)**
- Implement `POST/GET/PATCH/DELETE /deals`
- Implement in-memory store (`memory_store.py`)
- Write unit tests for all Deal endpoints

**Milestone 1.2 — Documents API (Days 9–11)**
- Implement `POST /deals/:id/documents` (multipart upload)
- Implement file parsing: PDF (PyMuPDF), XLSX (openpyxl), DOCX (python-docx), CSV (pandas)
- Implement `GET /deals/:id/documents` and `GET /documents/:id/text`
- Write unit tests for parsers

**Milestone 1.3 — Agent Run API (Days 12–14)**
- Implement `POST /deals/:id/agents/run` (async, returns run ID)
- Implement `GET /agents/runs/:id/stream` (SSE)
- Implement `GET /agents/runs/:id` (run details)
- Implement LLM client (`llm/client.py`) with retry logic
- Write integration test: trigger fake agent run, stream 5 progress events

**Milestone 1.4 — Outputs + Tasks API (Days 15–16)**
- Implement `GET /deals/:id/outputs`, `GET /outputs/:id/download`
- Implement `PATCH /outputs/:id/review`, `POST /outputs/:id/revise`
- Implement Tasks API (CRUD)
- Implement Settings API

### 3.2 Exit Criteria
- [ ] Full Postman/httpx test suite passes for all 17 endpoints
- [ ] File upload of sample PDF, XLSX, DOCX → text extracted successfully
- [ ] SSE stream sends 5 mock events then `complete` event
- [ ] All endpoints return correct error codes per spec (doc 06)

---

## 4. Phase 2 — Agent Framework + Financial Modeling Agent
**Duration:** Days 17–27  
**Goal:** The agent framework is working. The Financial Modeling agent produces real XLSX outputs.

### 4.1 Milestones

**Milestone 2.1 — Base Agent Framework (Days 17–19)**
- Implement `base_agent.py` (abstract class with `run()`, `think()`, `act()`, `observe()` methods)
- Implement `orchestrator/agent.py` (routing logic)
- Implement `prompt_builder.py` (system prompts for each agent type)
- Implement ReAct loop with reasoning steps logging

**Milestone 2.2 — Computation Engine: DCF (Days 20–22)**
- Implement `DCFEngine` class with all computation steps (doc 08 sec. 3)
- Implement sensitivity table builder
- Write unit tests: verify DCF output on known inputs (e.g., test case from IB textbook)
- Tolerance: ±0.1% on enterprise value vs. known answer

**Milestone 2.3 — Excel Writer Tool + DCF Template (Days 23–25)**
- Build `excel_writer/workbook_builder.py`
- Build `templates/excel/dcf_template.xlsx` skeleton
- Implement tool: write DCF outputs into template
- Produce sample DCF XLSX from test data

**Milestone 2.4 — Financial Modeling Agent End-to-End (Days 26–27)**
- Connect Financial Modeling Agent to DCF Engine + Excel Writer
- Test: upload sample income statement → trigger DCF agent → receive XLSX
- Validate: numbers in XLSX match DCF Engine output exactly
- Implement Hallucination Guard for modeling agent

### 4.2 Exit Criteria
- [ ] `POST /deals/:id/agents/run` with `agent_type: "modeling", task_name: "dcf_model"` → produces downloadable XLSX
- [ ] DCF XLSX has correct tabs: Revenue Projections, EBITDA, UFCF, DCF, Sensitivity
- [ ] Hallucination Guard runs and flags any numbers not found in source documents
- [ ] Reasoning steps logged to `agent_runs` table with all 5+ steps visible

---

## 5. Phase 3 — Full Agent Suite + All Tools
**Duration:** Days 28–38  
**Goal:** All 6 agents are working. All 7 tools are implemented. PDF and DOCX generation is live.

### 5.1 Build Order (dependencies respected)

```
Day 28–29: LBO Engine + LBO Excel output (Financial Modeling Agent, task 2)
Day 30:    CCA Engine + CCA Excel output (Financial Modeling Agent, task 3)
Day 31–32: PDF Generator Tool + Pitchbook Template
Day 33–34: Pitchbook Agent (12-slide generation)
Day 35:    Due Diligence Agent + Risk Classifier
Day 36:    Market Research Agent + Buyer Universe builder
Day 37:    Doc Drafter Agent + Word Generator + CIM template
Day 38:    Coordination Agent + Meeting Notes processor
```

### 5.2 Per-Agent Acceptance

| Agent | Minimum Viable Output |
|---|---|
| Financial Modeling (LBO) | XLSX with Sources & Uses, debt schedule, 5-yr model, IRR/MOIC |
| Financial Modeling (CCA) | XLSX with 5+ comps, multiples table, implied EV range |
| Pitchbook | 12-slide PDF with cover, transaction overview, company overview, market, financials, valuation, appendix |
| Due Diligence | PDF risk report with categorized flags (Financial/Legal/Operational), severity ratings |
| Market Research | PDF brief with industry overview, market size, key players, comp transactions, buyer universe |
| Doc Drafter | DOCX CIM draft: executive summary, business overview, market overview, financial summary |
| Coordination | Markdown summary with decisions, action items, open questions; auto-populated task cards |

### 5.3 Exit Criteria for Phase 3
- [ ] All 6 agents produce downloadable outputs for their core task
- [ ] All outputs use consistent B&W professional formatting
- [ ] Hallucination Guard runs on all agents that output financial figures
- [ ] Agent run completes in < 3 minutes for all task types on Colab T4

---

## 6. Phase 4 — Frontend + UX
**Duration:** Days 39–46  
**Goal:** Full working UI. Users can perform complete end-to-end workflows without touching the API directly.

### 6.1 Build Order

```
Day 39:    Dashboard + New Deal form + Deal list
Day 40:    Deal Workspace shell (tabs, routing)
Day 41:    Documents tab (upload zone, file list, parse status)
Day 42:    Agents tab (agent cards, input panels, Run button)
Day 43:    SSE integration (reasoning panel, progress bar)
Day 44:    Outputs tab (file list, PDF preview, approve/revise)
Day 45:    Task board (Kanban), Activity log
Day 46:    Global Settings page + Error/Empty states + polish
```

### 6.2 UI Acceptance Criteria

| Screen | Must Pass |
|---|---|
| Dashboard | Shows deal list, displays empty state, New Deal button visible |
| New Deal | Validates all required fields, creates deal, redirects correctly |
| Documents | Drag-and-drop works, shows parse status, allows delete |
| Agents | Each agent card renders, inputs are context-appropriate, Run button triggers API |
| Reasoning Panel | Shows live SSE events during run, confidence badge appears on completion |
| Outputs | PDF renders in browser, download works, Approve / Request Revision work |
| Task Board | Tasks grouped by status, drag-and-drop between columns, manual task creation works |
| Global Settings | LLM endpoint URL can be saved and tested |

### 6.3 Design Compliance Checklist
- [ ] Primary background: `#FFFFFF`
- [ ] Primary text: `#0A0A0A`
- [ ] Secondary text: `#6B6B6B`
- [ ] Borders: `#E5E5E5`
- [ ] Focus rings: `#0A0A0A` (1px solid)
- [ ] Primary button: black fill, white text, no border radius > 4px
- [ ] No color other than black/white/grey anywhere in UI
- [ ] Font: Inter or system-ui, weight 400/500/600 only
- [ ] All generated PDFs/XLSX match the same B&W visual language

---

## 7. Phase 5 — Integration, Testing & Polish
**Duration:** Days 47–51  
**Goal:** End-to-end user workflows pass. All tests green. System is ready for beta use.

### 7.1 Testing Sprint

| Day | Focus |
|---|---|
| 47 | End-to-end test: full DCF workflow (upload → agent run → download XLSX) |
| 48 | End-to-end test: pitchbook workflow + DD review workflow |
| 49 | Load/stress: run all 6 agents back-to-back on Colab, measure latency |
| 50 | Bug bash: all error states, edge cases, empty states |
| 51 | Final polish: copy, tooltips, README, deployment guide |

### 7.2 Launch Readiness Checklist
- [ ] All P0 user stories pass their acceptance criteria
- [ ] No critical (P0) bugs open
- [ ] Colab setup notebook runs top-to-bottom without errors
- [ ] README contains 5-minute quick-start guide
- [ ] Sample deal with all 6 agent outputs can be generated end-to-end in < 30 minutes
- [ ] Disclaimer visible on all generated outputs
- [ ] Confidential data from testing is purged

---

## 8. Version Roadmap

| Version | Timeline | Key Additions |
|---|---|---|
| v1.0 (MVP) | Weeks 1–8 | All core agents, Colab LLM, B&W UI, local storage |
| v1.1 | +4 weeks | Fine-tuned model (Unsloth LoRA on IB datasets), improved output quality |
| v2.0 | +3 months | Persistent DB, user auth, real market data (yFinance), deal memory (vector DB) |
| v2.1 | +1 month | Multi-user, deal sharing, Slack notifications |
| v3.0 | +6 months | Production LLM hosting (Replicate/Modal), Bloomberg API, enterprise features |

---

*End of Document — 10-development-phases.md*
