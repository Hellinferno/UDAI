# 06 — API Contracts
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

This document defines all HTTP API contracts between:
- **React SPA ↔ Orchestration Backend (FastAPI)**
- **Orchestration Backend ↔ Colab LLM Inference Server**

**Base URL (Orchestration Backend):** `http://localhost:8000/api/v1`  
**Base URL (Colab LLM Server):** `{COLAB_NGROK_URL}/api` (configured in settings)  
**Protocol:** REST + Server-Sent Events (SSE) for streaming  
**Content-Type:** `application/json` (except file uploads: `multipart/form-data`)  
**Auth (v1):** None (single-user local deployment)

---

## 2. Standard Response Envelope

All responses follow this envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "timestamp": "2025-01-15T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AGENT_TIMEOUT",
    "message": "The agent did not complete within the timeout window.",
    "details": {}
  },
  "meta": {
    "timestamp": "2025-01-15T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

---

## 3. Deals API

### `POST /deals` — Create a New Deal

**Request:**
```json
{
  "name": "Project Falcon",
  "company_name": "Nexus Pharma Inc.",
  "deal_type": "ma_sellside",
  "industry": "Healthcare / Pharmaceuticals",
  "deal_stage": "preliminary",
  "notes": "Sell-side mandate for founder-owned pharma company, ~$150M revenue"
}
```

**Response `201`:**
```json
{
  "success": true,
  "data": {
    "id": "deal_9f3a1c2d",
    "name": "Project Falcon",
    "company_name": "Nexus Pharma Inc.",
    "deal_type": "ma_sellside",
    "industry": "Healthcare / Pharmaceuticals",
    "deal_stage": "preliminary",
    "notes": "...",
    "created_at": "2025-01-15T10:30:00Z",
    "document_count": 0,
    "output_count": 0
  }
}
```

**Validation Errors `422`:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "company_name": ["Field is required"],
      "deal_type": ["Invalid value. Must be one of: ma_buyside, ma_sellside, ipo, ..."]
    }
  }
}
```

---

### `GET /deals` — List All Deals

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | all | Filter by stage: preliminary / active / final / closed |
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Pagination offset |
| `sort` | string | created_at_desc | Sort order |

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "deals": [
      {
        "id": "deal_9f3a1c2d",
        "name": "Project Falcon",
        "company_name": "Nexus Pharma Inc.",
        "deal_type": "ma_sellside",
        "deal_stage": "preliminary",
        "created_at": "2025-01-15T10:30:00Z",
        "document_count": 5,
        "output_count": 3,
        "last_activity": "2025-01-15T14:22:00Z"
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

---

### `GET /deals/:deal_id` — Get Deal Details

**Response `200`:** Full deal object including embedded document list, output list, task list.

### `PATCH /deals/:deal_id` — Update Deal

**Request:** Partial update of any deal field.

### `DELETE /deals/:deal_id` — Archive Deal

Soft-deletes (sets `is_archived = true`).

---

## 4. Documents API

### `POST /deals/:deal_id/documents` — Upload Documents

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `files` | File[] | One or more files (.pdf, .docx, .xlsx, .csv) |
| `category` | string | Optional: 'financial', 'legal', 'corporate', 'tax', 'operational' |

**Response `201`:**
```json
{
  "success": true,
  "data": {
    "uploaded": [
      {
        "id": "doc_a1b2c3",
        "filename": "income_statement_2024.xlsx",
        "file_type": "xlsx",
        "file_size_bytes": 45231,
        "parse_status": "processing",
        "uploaded_at": "2025-01-15T10:35:00Z"
      }
    ],
    "failed": []
  }
}
```

---

### `GET /deals/:deal_id/documents` — List Documents

**Response `200`:** Array of document objects with parse_status.

### `DELETE /deals/:deal_id/documents/:doc_id` — Delete Document

### `GET /deals/:deal_id/documents/:doc_id/text` — Get Parsed Text

Returns extracted plain text content for a document (used internally by agents).

---

## 5. Agent API

### `POST /deals/:deal_id/agents/run` — Trigger Agent Run

This is the primary endpoint. The frontend calls this to invoke any agent.

**Request:**
```json
{
  "agent_type": "modeling",
  "task_name": "dcf_model",
  "parameters": {
    "model_type": "dcf",
    "projection_years": 5,
    "wacc_override": null,
    "terminal_growth_rate": 0.025,
    "document_ids": ["doc_a1b2c3", "doc_d4e5f6"],
    "additional_context": "Company operates in high-growth SaaS segment with 35% YoY revenue growth"
  }
}
```

**Valid `agent_type` values:**
- `orchestrator` — Routes to correct agent automatically
- `modeling` — Financial modeling
- `pitchbook` — Presentation generation
- `due_diligence` — Document review and risk flagging
- `research` — Market and industry research
- `doc_drafter` — CIM and deal document writing
- `coordination` — Meeting notes and task tracking

**Valid `task_name` values per agent:**

| agent_type | task_name options |
|---|---|
| modeling | `dcf_model`, `lbo_model`, `comparable_analysis` |
| pitchbook | `full_pitchbook`, `executive_summary_slides`, `single_slide_revision` |
| due_diligence | `full_dd_review`, `dd_checklist`, `risk_summary` |
| research | `industry_overview`, `buyer_universe`, `target_universe`, `comp_transactions` |
| doc_drafter | `cim_draft`, `executive_summary`, `deal_teaser`, `market_overview_section` |
| coordination | `process_meeting_notes`, `generate_task_list`, `deal_status_report` |

**Response `202 Accepted`:**
```json
{
  "success": true,
  "data": {
    "run_id": "run_x7y8z9",
    "agent_type": "modeling",
    "task_name": "dcf_model",
    "status": "queued",
    "stream_url": "/api/v1/agents/runs/run_x7y8z9/stream",
    "created_at": "2025-01-15T10:36:00Z"
  }
}
```

### Modeling Task Parameters (`agent_type=modeling`, `task_name=dcf_model`)

The following optional parameters are now supported for advanced scenario and risk analysis:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario_probability_weights` | object | `{ "bear": 0.25, "base": 0.50, "bull": 0.25 }` | Probability weights for scenario-planning expected value. Weights are normalized server-side. |
| `monte_carlo_iterations` | int | `1500` | Number of Monte Carlo paths (`>= 100`). |
| `monte_carlo_seed` | int | `42` | Random seed for deterministic replay. |
| `monte_carlo_growth_volatility` | float | `0.015` | Std-dev of growth shock. |
| `monte_carlo_margin_volatility` | float | `0.04` | Std-dev of margin shock. |
| `monte_carlo_wacc_volatility` | float | `0.01` | Std-dev of WACC shock. |
| `monte_carlo_tgr_volatility` | float | `0.003` | Std-dev of terminal-growth shock. |
| `monte_carlo_var_confidence_level` | float | `0.95` | Tail confidence for VaR/CVaR reporting. Accepted range: `0.80` to `0.995`. |
| `monte_carlo_correlation_matrix` | object | internal default | Optional correlation matrix across factors `growth`, `margin`, `wacc`, `tgr`. |

`monte_carlo_correlation_matrix` shape example:
```json
{
  "growth": { "margin": 0.60, "wacc": -0.40, "tgr": 0.30 },
  "margin": { "wacc": -0.20, "tgr": 0.20 },
  "wacc": { "tgr": 0.50 }
}
```

### Modeling Result Contract Additions

When run details include valuation output, the object now contains a `parallel_analysis` block with worker-level outputs:

```json
{
  "parallel_analysis": {
    "dcf_worker": {
      "enterprise_value": 12345.67,
      "equity_value": 11234.56,
      "implied_share_price": 145.12,
      "wacc": 0.112,
      "terminal_growth_rate": 0.03
    },
    "comps_worker": {
      "method": "ev_ebitda_comps",
      "industry": "IT Services",
      "multiple_band": { "bear": 14.0, "base": 18.0, "bull": 22.0 },
      "scenarios": { "bear": {}, "base": {}, "bull": {} }
    },
    "financial_statement_worker": {
      "industry_context": "technology",
      "ratios": {},
      "analysis": {
        "overall_health": { "status": "Good", "score": 2.75 },
        "recommendations": []
      },
      "trend_analysis": {
        "signal": "Improving",
        "score": 2,
        "metrics": {
          "current_ratio": { "signal": "Improving", "start": 1.4, "end": 2.1, "series": [1.4, 1.8, 2.1] },
          "debt_to_equity": { "signal": "Improving", "start": 0.9, "end": 0.4, "series": [0.9, 0.6, 0.4] }
        },
        "period_count": 3
      }
    },
    "scenario_planning_worker": {
      "expected_value": 105.0,
      "weights": { "bear": 0.2, "base": 0.5, "bull": 0.3 },
      "metric": "share_price",
      "details": []
    },
    "monte_carlo_worker": {
      "iterations": 1500,
      "metric": "share_price",
      "summary": {
        "mean": 147.9,
        "median": 145.8,
        "p5": 113.4,
        "p95": 185.1,
        "probability_of_loss": 0.02,
        "var_confidence_level": 0.95,
        "var_value": 113.4,
        "cvar_value": 106.2,
        "var_downside_from_mean": 34.5,
        "cvar_downside_from_mean": 41.7
      },
      "distribution_preview": {
        "min": 92.1,
        "max": 223.8,
        "sample": [92.1, 104.4, 118.8]
      },
      "assumptions": {
        "growth_volatility": 0.015,
        "margin_volatility": 0.04,
        "wacc_volatility": 0.01,
        "tgr_volatility": 0.003,
        "seed": 42,
        "correlation_matrix": [[1.0, 0.45, -0.35, 0.2], [0.45, 1.0, -0.25, 0.15], [-0.35, -0.25, 1.0, 0.4], [0.2, 0.15, 0.4, 1.0]]
      }
    },
    "synthesis": "Parallel synthesis complete..."
  }
}
```

---

### `GET /agents/runs/:run_id/stream` — Stream Agent Progress (SSE)

**Protocol:** Server-Sent Events  
**Content-Type:** `text/event-stream`

**Event Types:**
```
event: step
data: {"step": 1, "type": "thought", "content": "Parsing income statement from uploaded Excel file..."}

event: step
data: {"step": 2, "type": "action", "content": "Calling tool: parse_excel", "tool_input": "income_statement_2024.xlsx"}

event: step
data: {"step": 3, "type": "observation", "content": "Extracted 5 years of revenue data: [12.5M, 17.8M, 24.1M, 31.5M, 40.2M]"}

event: step
data: {"step": 4, "type": "thought", "content": "Revenue CAGR is 33.9%. Applying DCF methodology with WACC=10%..."}

event: progress
data: {"percent_complete": 65, "current_step": "Building DCF sensitivity table"}

event: complete
data: {"run_id": "run_x7y8z9", "status": "completed", "output_id": "out_p1q2r3", "confidence_score": 0.87}

event: error
data: {"run_id": "run_x7y8z9", "status": "failed", "error_code": "LLM_TIMEOUT", "message": "LLM inference server did not respond"}
```

---

### `GET /agents/runs/:run_id` — Get Run Details

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "id": "run_x7y8z9",
    "deal_id": "deal_9f3a1c2d",
    "agent_type": "modeling",
    "task_name": "dcf_model",
    "status": "completed",
    "reasoning_steps": [
      {"step": 1, "type": "thought", "content": "..."},
      {"step": 2, "type": "action", "content": "...", "tool": "parse_excel"},
      {"step": 3, "type": "observation", "content": "..."}
    ],
    "confidence_score": 0.87,
    "started_at": "2025-01-15T10:36:05Z",
    "completed_at": "2025-01-15T10:37:42Z",
    "duration_seconds": 97,
    "output_ids": ["out_p1q2r3"]
  }
}
```

---

## 6. Outputs API

### `GET /deals/:deal_id/outputs` — List Outputs

**Response `200`:** Array of output objects.

### `GET /outputs/:output_id` — Get Output Metadata

### `GET /outputs/:output_id/download` — Download Output File

**Response:** Binary file stream with appropriate `Content-Type` and `Content-Disposition: attachment` headers.

### `PATCH /outputs/:output_id/review` — Update Review Status

**Request:**
```json
{
  "review_status": "approved",
  "reviewer_notes": "Looks good, minor formatting adjustment needed on sensitivity table"
}
```

**Valid `review_status` values:** `approved`, `revision_requested`, `archived`

---

### `POST /outputs/:output_id/revise` — Request Revision

**Request:**
```json
{
  "revision_instructions": "Change the discount rate assumption from 10% to 12% and regenerate the sensitivity table",
  "sections": ["assumptions", "sensitivity_table"]
}
```

**Response:** New `AgentRun` object (same as `/agents/run` response).

---

## 7. Tasks API

### `GET /deals/:deal_id/tasks` — List Tasks

### `POST /deals/:deal_id/tasks` — Create Manual Task

**Request:**
```json
{
  "title": "Send NDA to potential buyer",
  "description": "Draft and send NDA to Apollo Management contact",
  "owner": "John Smith",
  "priority": "high",
  "due_date": "2025-01-20"
}
```

### `PATCH /tasks/:task_id` — Update Task Status

**Request:**
```json
{
  "status": "completed",
  "owner": "John Smith"
}
```

---

## 8. Settings API

### `GET /settings` — Get All Settings

### `PUT /settings/:key` — Update a Setting

**Request:**
```json
{
  "value": "https://abc123.ngrok.io"
}
```

**Critical settings:**
- `llm_endpoint_url` — Colab ngrok URL

---

## 9. Colab LLM Inference API (Internal)

This API is exposed by the FastAPI server running in Google Colab.

### `POST /generate` — Generate LLM Completion

**Request:**
```json
{
  "prompt": "You are a senior Investment Banking Analyst...\n\nTask: Build a 5-year DCF model...",
  "system_prompt": "You are an expert investment banking analyst...",
  "max_tokens": 4096,
  "temperature": 0.2,
  "stream": false,
  "response_format": "json"
}
```

**Response `200`:**
```json
{
  "completion": "{ \"revenue_projections\": [40.2, 53.5, 68.9, 87.1, 107.5], \"wacc\": 0.10, ... }",
  "tokens_used": {
    "prompt": 1247,
    "completion": 892,
    "total": 2139
  },
  "model": "llama3-8b-ib-analyst",
  "latency_ms": 4231
}
```

### `GET /health` — Health Check

**Response `200`:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "llama3-8b-ib-analyst",
  "gpu_memory_used_gb": 6.2,
  "gpu_memory_total_gb": 15.0
}
```

---

## 10. Error Codes Reference

| Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request body failed validation |
| `DEAL_NOT_FOUND` | 404 | Deal ID does not exist |
| `DOCUMENT_NOT_FOUND` | 404 | Document ID does not exist |
| `RUN_NOT_FOUND` | 404 | Agent run ID does not exist |
| `OUTPUT_NOT_FOUND` | 404 | Output ID does not exist |
| `UNSUPPORTED_FILE_TYPE` | 400 | Uploaded file type not supported |
| `FILE_TOO_LARGE` | 413 | File exceeds 50MB limit |
| `AGENT_UNAVAILABLE` | 503 | LLM backend is offline |
| `AGENT_TIMEOUT` | 504 | Agent did not complete in time |
| `AGENT_ERROR` | 500 | Agent encountered an internal error |
| `HALLUCINATION_GUARD` | 200 | Output flagged for low confidence (non-blocking) |
| `PARSE_FAILED` | 422 | Document could not be parsed |

---

*End of Document — 06-api-contracts.md*
