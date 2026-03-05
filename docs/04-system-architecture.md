# 04 — System Architecture
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Architecture Philosophy

AIBAA is designed around three principles:

1. **Agent-First Design** — Every core feature is an AI agent with defined inputs, tools, and outputs.
2. **Colab-Native LLM Inference** — The AI backbone runs on Google Colab + Unsloth, connected via a lightweight API gateway.
3. **Thin Frontend** — The UI is a stateless React SPA that communicates with a FastAPI orchestration backend.

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
│                                                          │
│   ┌─────────────────────────────────────────────────┐   │
│   │         React SPA (B&W Professional UI)          │   │
│   │  Dashboard | Deal Workspace | Agent Panel        │   │
│   │  Document Upload | Output Preview | Task Tracker │   │
│   └───────────────────────┬─────────────────────────┘   │
└───────────────────────────┼─────────────────────────────┘
                            │ HTTPS / REST + SSE
┌───────────────────────────▼─────────────────────────────┐
│                 ORCHESTRATION LAYER                       │
│                                                          │
│   ┌─────────────────────────────────────────────────┐   │
│   │          FastAPI Backend (Python 3.11)           │   │
│   │                                                  │   │
│   │   ┌──────────────────────────────────────────┐  │   │
│   │   │         Orchestrator Agent               │  │   │
│   │   │  (Routes tasks → selects sub-agent)      │  │   │
│   │   └──────────────────────────────────────────┘  │   │
│   │                                                  │   │
│   │   Sub-Agent Registry:                            │   │
│   │   ┌──────────┐ ┌──────────┐ ┌───────────────┐  │   │
│   │   │ Modeling │ │Pitchbook │ │ Due Diligence  │  │   │
│   │   └──────────┘ └──────────┘ └───────────────┘  │   │
│   │   ┌──────────┐ ┌──────────┐ ┌───────────────┐  │   │
│   │   │ Research │ │  Doc     │ │ Coordination  │  │   │
│   │   │ Agent    │ │ Drafter  │ │ Agent         │  │   │
│   │   └──────────┘ └──────────┘ └───────────────┘  │   │
│   │                                                  │   │
│   │   Tool Registry:                                 │   │
│   │   Python Exec | File Parser | Doc Generator     │   │
│   │   Web Search (stub) | Template Engine           │   │
│   └───────────────────────┬──────────────────────┘  │   │
└───────────────────────────┼─────────────────────────────┘
                            │ HTTP (ngrok tunnel)
┌───────────────────────────▼─────────────────────────────┐
│                    LLM INFERENCE LAYER                    │
│                                                          │
│   ┌─────────────────────────────────────────────────┐   │
│   │         Google Colab Session (GPU: T4/A100)      │   │
│   │                                                  │   │
│   │   ┌─────────────────────────────────────────┐   │   │
│   │   │     Unsloth Fine-tuned LLM Engine        │   │   │
│   │   │  (Llama-3 / Mistral / Qwen base model)  │   │   │
│   │   │  + Domain fine-tune: IB analyst tasks    │   │   │
│   │   └─────────────────────────────────────────┘   │   │
│   │                                                  │   │
│   │   ┌─────────────────────────────────────────┐   │   │
│   │   │     FastAPI Inference Server (Colab)     │   │   │
│   │   │  Exposed via ngrok tunnel                │   │   │
│   │   └─────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    STORAGE LAYER                          │
│                                                          │
│   Session Storage (in-memory, FastAPI):                  │
│   - Deal metadata                                        │
│   - Uploaded file buffers                                │
│   - Agent run logs                                       │
│                                                          │
│   File System (local/temp):                              │
│   - Uploaded raw files                                   │
│   - Generated output files (XLSX, PDF, DOCX)            │
│                                                          │
│   (v2: SQLite or Supabase for persistence)               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 React SPA (Frontend)
| Component | Technology | Responsibility |
|---|---|---|
| UI Framework | React 18 + Vite | Component rendering, routing |
| Styling | Tailwind CSS (black/white tokens) | Visual design system |
| File Upload | react-dropzone | Drag-and-drop document upload |
| PDF Preview | react-pdf | Inline PDF rendering |
| SSE Client | native EventSource API | Real-time agent progress streaming |
| State Management | Zustand | Client-side deal/agent state |
| HTTP Client | Axios | API calls to orchestration backend |
| Routing | React Router v6 | Page navigation |

### 3.2 Orchestration Backend (FastAPI)
| Component | Technology | Responsibility |
|---|---|---|
| API Framework | FastAPI (Python 3.11) | REST endpoints, SSE streaming |
| Orchestrator | LangGraph / custom agent loop | Task routing and agent lifecycle |
| File Parsing | PyMuPDF, python-docx, openpyxl | Read uploaded documents |
| Output Generation | openpyxl, python-docx, ReportLab | Create XLSX, DOCX, PDF outputs |
| Tool Registry | Python modules | Code exec, search, formatting |
| Session Store | Python dict (in-memory) | Deal context per session |
| Background Tasks | FastAPI BackgroundTasks | Async agent execution |

### 3.3 LLM Inference Server (Colab + Unsloth)
| Component | Technology | Responsibility |
|---|---|---|
| LLM Runtime | Unsloth + HuggingFace Transformers | Fast 4-bit quantized inference |
| Base Model | Llama-3-8B-Instruct (or Mistral-7B) | Foundation language model |
| Fine-tuning | Unsloth LoRA fine-tuning | IB domain specialization |
| Inference API | FastAPI (Colab-side) | Accept prompts, return completions |
| Tunnel | ngrok / Cloudflare Tunnel | Expose Colab to orchestration backend |
| Context Management | Custom prompt templates | System prompts per agent |

---

## 4. Agent Architecture

Each sub-agent follows the **ReAct (Reason + Act)** pattern:

```
System Prompt (Agent Role)
→ Input Context (deal info + uploaded docs)
→ Think: "What do I need to do?"
→ Act: Call Tool (parse_file / run_python / format_output)
→ Observe: Tool result
→ Think: "Does this meet the requirement?"
→ Repeat or Finalize
→ Output: Structured result + confidence score
```

### Agent Definitions

| Agent | System Prompt Role | Primary Tools | Output |
|---|---|---|---|
| Orchestrator | "Route user requests to the correct analyst agent." | all agents | Task assignment |
| Financial Modeling | "You are a senior IB analyst building financial models." | python_exec, excel_writer | XLSX model |
| Pitchbook | "You are an IB analyst creating client pitch presentations." | doc_generator, chart_builder | PDF/PPTX |
| Due Diligence | "You are a legal/financial due diligence reviewer." | pdf_parser, risk_classifier | PDF report |
| Market Research | "You are an equity research analyst." | web_search (stub), data_formatter | PDF brief |
| Doc Drafter | "You are drafting a Confidential Information Memorandum." | doc_template, financial_parser | DOCX/PDF |
| Coordinator | "You are a deal coordination specialist." | task_extractor, log_writer | Markdown / XLSX |

---

## 5. Data Flow for a Typical Task

### Example: User requests DCF model

```
1. User fills DCF parameters in UI → clicks "Run"
2. React SPA → POST /api/agents/run { deal_id, agent: "modeling", task: "dcf", params: {...} }
3. Orchestration Backend:
   a. Loads deal context (uploaded financials)
   b. Parses uploaded XLSX using openpyxl
   c. Constructs LLM prompt: "Given these financials: {...}, build a 5-year DCF model..."
   d. POST → Colab inference server /generate
4. Colab (Unsloth LLM):
   a. Receives prompt
   b. Returns structured JSON: { "revenue_projections": [...], "wacc": 0.10, "terminal_value": ... }
5. Orchestration Backend:
   a. Receives LLM output
   b. Passes to python_exec tool → runs financial calculation logic
   c. Writes XLSX using openpyxl
   d. Streams progress back to frontend via SSE
6. React SPA:
   a. SSE updates reasoning panel in real-time
   b. Final output file URL received
   c. File preview + download link shown to user
```

---

## 6. Communication Protocols

| Connection | Protocol | Details |
|---|---|---|
| React SPA ↔ FastAPI Backend | REST (HTTPS) + SSE | REST for requests, SSE for streaming progress |
| FastAPI Backend ↔ Colab | HTTP (via ngrok) | POST /generate with prompt payload |
| File Upload | Multipart HTTP | Files sent as form-data |
| Colab ↔ Internet (stub) | HTTPS | Web search for market data (future) |

---

## 7. Security Considerations

| Risk | Mitigation |
|---|---|
| Exposed ngrok URL | Auth token on Colab inference endpoint |
| Uploaded sensitive documents | Files stored in-memory only; cleared on session end |
| LLM hallucination on financial data | Post-processing verification step: cross-check LLM output vs uploaded source |
| No auth in v1 | Single-user local deployment; v2 adds JWT auth |

---

## 8. Scalability Path (Post-v1)

| Concern | v1 Approach | v2 Path |
|---|---|---|
| LLM Hosting | Colab (session-based) | Replicate / Modal / AWS SageMaker |
| Storage | In-memory / local FS | Supabase / S3 |
| Multi-user | Single user | JWT auth + multi-tenant DB |
| Persistent memory | Session state | Vector DB (ChromaDB/Pinecone) for deal memory |
| Real market data | Stub/mock | Bloomberg API / yFinance / Alpha Vantage |

---

*End of Document — 04-system-architecture.md*
