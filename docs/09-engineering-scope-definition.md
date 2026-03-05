# 09 — Engineering Scope Definition
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Purpose

This document precisely defines **what will be built** vs. **what will not be built** in the MVP (v1.0), drawing a clear line between engineering commitments and deferred work. It is the primary reference for developer sprint planning.

---

## 2. Engineering Boundaries

### 2.1 IN SCOPE — v1.0 MVP

#### Frontend (React SPA)
| # | Feature | Acceptance Reference |
|---|---|---|
| FE-01 | Dashboard with deal list | US-001, AC-4 |
| FE-02 | New Deal form + validation | US-001 |
| FE-03 | Deal workspace with 5 tabs (Overview, Documents, Agents, Outputs, Settings) | US-001 |
| FE-04 | File upload zone (drag-and-drop, multi-file) | US-002 |
| FE-05 | Document list with status badges | US-002 |
| FE-06 | Agent card per agent type (6 agents) | US-006, US-008, US-010 |
| FE-07 | Agent input panel (context-sensitive per agent) | US-003–US-012 |
| FE-08 | SSE-based reasoning panel (live updates) | US-015 |
| FE-09 | Progress indicator during agent runs | US-006, AC-2 |
| FE-10 | Output file list with download + preview | US-003, US-006 |
| FE-11 | PDF in-browser preview | US-006, AC-3 |
| FE-12 | Approve / Request Revision actions on outputs | FR-10 |
| FE-13 | Task tracker board (Kanban: To Do / In Progress / Done) | US-013 |
| FE-14 | Activity log in deal overview | US-013 |
| FE-15 | Global Settings page (LLM endpoint URL) | NFR-02 |
| FE-16 | Black-and-white design system (full implementation) | US-014 |
| FE-17 | Hallucination warning badge on outputs | US-015, AC-3 |
| FE-18 | Error states (offline backend, parse failure, timeout) | 03-IA sec. 8 |
| FE-19 | Empty states for all list views | 03-IA sec. 7 |
| FE-20 | Responsive layout (min 1280px) | US-014, AC-4 |

#### Backend (FastAPI Orchestration)
| # | Feature | Acceptance Reference |
|---|---|---|
| BE-01 | `POST /deals` — Create deal | US-001 |
| BE-02 | `GET /deals` — List deals | FE-01 |
| BE-03 | `GET /deals/:id` — Get deal | FE-03 |
| BE-04 | `PATCH /deals/:id` — Update deal | US-013 |
| BE-05 | `POST /deals/:id/documents` — File upload (multipart) | US-002 |
| BE-06 | `GET /deals/:id/documents` — List documents | FE-04 |
| BE-07 | `POST /deals/:id/agents/run` — Trigger agent | US-003–US-012 |
| BE-08 | `GET /agents/runs/:id/stream` — SSE stream | FE-08 |
| BE-09 | `GET /agents/runs/:id` — Run details | FE-10 |
| BE-10 | `GET /deals/:id/outputs` — List outputs | FE-10 |
| BE-11 | `GET /outputs/:id/download` — File download | FE-10 |
| BE-12 | `PATCH /outputs/:id/review` — Review status update | FE-12 |
| BE-13 | `POST /outputs/:id/revise` — Request revision | FE-12 |
| BE-14 | `GET /deals/:id/tasks` — Task list | FE-13 |
| BE-15 | `POST /deals/:id/tasks` — Manual task creation | US-013 |
| BE-16 | `PATCH /tasks/:id` — Update task | US-013 |
| BE-17 | `GET/PUT /settings/:key` — Settings CRUD | FE-15 |
| BE-18 | In-memory session store (dict-based) | 05-schema |
| BE-19 | Background task execution (non-blocking agent runs) | FR-01 |
| BE-20 | File parsing: PDF, DOCX, XLSX, CSV | US-002, FR-02 |

#### Agents (Python)
| # | Agent | Tasks In Scope |
|---|---|---|
| AG-01 | Orchestrator | Route incoming request to correct sub-agent |
| AG-02 | Financial Modeling | DCF model, LBO model, CCA |
| AG-03 | Pitchbook | Full pitchbook generation (12-slide structure) |
| AG-04 | Due Diligence | Full DD review, risk summary report, DD checklist |
| AG-05 | Market Research | Industry overview brief, buyer universe list |
| AG-06 | Doc Drafter | CIM draft (4 sections), executive summary, deal teaser |
| AG-07 | Coordination | Process meeting notes, extract action items, deal status report |

#### Tools (Python)
| # | Tool | Capability |
|---|---|---|
| TL-01 | PDF Parser | Extract text via PyMuPDF |
| TL-02 | Excel Parser | Read structured data via openpyxl |
| TL-03 | Word Parser | Extract text via python-docx |
| TL-04 | CSV Parser | Parse tabular data via pandas |
| TL-05 | Excel Writer | Build XLSX models with formatting + charts |
| TL-06 | PDF Generator | Create professional B&W PDFs via ReportLab |
| TL-07 | Word Generator | Create DOCX documents via python-docx |
| TL-08 | Python Executor | Run financial calculation code safely |
| TL-09 | Web Search (stub) | Return mock market data (real API deferred) |

#### Computation Engine
| # | Module | Spec Reference |
|---|---|---|
| CE-01 | DCF Engine (full 5-step) | 08-spec sec. 3 |
| CE-02 | LBO Engine (sources/uses, debt schedule, IRR) | 08-spec sec. 4 |
| CE-03 | CCA Engine (multiples computation) | 08-spec sec. 5 |
| CE-04 | Hallucination Guard | 08-spec sec. 6 |
| CE-05 | Output Verification Checklist | 08-spec sec. 7 |

#### Colab Integration
| # | Component | Scope |
|---|---|---|
| CO-01 | Colab setup notebook (environment + dependencies) | Install Unsloth, load model |
| CO-02 | Inference server (FastAPI on Colab) | `/generate` + `/health` endpoints |
| CO-03 | ngrok tunnel setup | Expose Colab server to local backend |
| CO-04 | Prompt template system | One system prompt per agent type |

#### Document Templates
| # | Template | Format |
|---|---|---|
| TP-01 | DCF model skeleton | XLSX |
| TP-02 | LBO model skeleton | XLSX |
| TP-03 | CCA model skeleton | XLSX |
| TP-04 | Pitchbook template (12-slide B&W) | PDF via ReportLab |
| TP-05 | DD risk report template | PDF via ReportLab |
| TP-06 | Research brief template | PDF via ReportLab |
| TP-07 | CIM document template | DOCX |

---

### 2.2 OUT OF SCOPE — v1.0 (Deferred to v2/v3)

| Feature | Reason Deferred | Target Version |
|---|---|---|
| User authentication / login | Single-user local deployment | v2 |
| Multi-user collaboration | Requires auth + multi-tenant DB | v2 |
| Persistent database (SQLite/PostgreSQL) | In-memory sufficient for MVP | v2 |
| Real Bloomberg / Capital IQ API | Licensed, cost, complexity | v2 |
| Real-time web search (live) | Requires API key + rate limiting | v2 |
| Mobile responsive design | Desktop financial tool | v2 |
| Deal sharing / export to Google Drive | Not in core workflow | v2 |
| Real-time deal collaboration | Complex infra | v3 |
| Vector DB for long-term deal memory | Nice-to-have for recall | v2 |
| Fine-tuning pipeline UI | Power user feature | v2 |
| Slack / email integration for task notifications | External integrations | v2 |
| Version history on outputs | Complex state management | v2 |
| Custom pitchbook color themes | B&W only in v1 | v2 |
| Audit trail export (compliance) | Enterprise feature | v3 |
| API key management UI | Power user feature | v2 |
| White-labeling / custom branding | Enterprise | v3 |

---

## 3. Technical Constraints

| Constraint | Detail |
|---|---|
| **LLM Runtime** | Must work on Google Colab free/pro tier (T4 GPU) |
| **LLM Memory** | 4-bit quantized model must fit in ≤ 15GB GPU VRAM |
| **Session Limit** | Colab sessions timeout after ~12 hours; design for graceful reconnect |
| **File Storage** | No cloud storage in v1; all files live on local filesystem |
| **Inference Latency** | Complex tasks may take 2–4 minutes; UI must handle gracefully with SSE |
| **No Real-Time Data** | Market data is stubbed; system must not present stub data as real |
| **Single User** | No concurrency requirements in v1 |
| **Python 3.11** | Target Python version for all backend code |
| **Node 18+** | Target Node version for frontend build |

---

## 4. Definition of Done (DoD)

A feature is **Done** when:

1. ✅ All acceptance criteria from doc `02` pass
2. ✅ Unit tests written and passing (≥ 80% coverage on new code)
3. ✅ API contract matches specification in doc `06` exactly
4. ✅ Code reviewed by at least one other person (or self-reviewed if solo)
5. ✅ No blocking linter errors
6. ✅ UI renders correctly at 1280px and 1440px
7. ✅ Error states handled (no unhandled exceptions surface to user)
8. ✅ Console is clean (no `console.error` or Python stack traces in production)
9. ✅ Feature demoed and verified against the PRD success metrics where applicable

---

## 5. Engineering Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Colab session disconnects mid-run | High | Medium | SSE reconnect logic; show "Resume" option in UI |
| LLM hallucinates financial figures | High | Critical | Hallucination Guard + human review badge (non-blocking) |
| PDF generation quality is poor | Medium | High | Build ReportLab templates in isolation, validate early |
| XLSX output formatting is broken | Medium | High | Template-driven Excel; test with real sample data |
| ngrok tunnel is slow / unreliable | Medium | Medium | Health check polling; fallback error messaging in UI |
| File parsing fails on edge-case formats | Medium | Medium | Graceful error + user prompt to re-upload clean file |
| LLM context window overflow on large docs | High | Medium | Chunk documents; summarize large files before injection |

---

## 6. Estimation Summary

| Area | Story Points (Fibonacci) | Estimated Dev Days |
|---|---|---|
| Frontend (React SPA) | 55 | 11 days |
| Backend API (FastAPI) | 34 | 7 days |
| Agent implementations (6 agents) | 55 | 11 days |
| Computation Engine (DCF/LBO/CCA) | 21 | 4 days |
| Tools (7 tools) | 21 | 4 days |
| Colab integration + inference server | 13 | 3 days |
| Document templates (7 templates) | 21 | 4 days |
| Fine-tuning (basic LoRA) | 13 | 3 days |
| Testing + QA | 21 | 4 days |
| **Total** | **254** | **~51 days (solo dev)** |

> **Note:** This assumes a single full-stack developer. A 2-person team (1 frontend, 1 backend/AI) would reduce to ~28 days.

---

*End of Document — 09-engineering-scope-definition.md*
