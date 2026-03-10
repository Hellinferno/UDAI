# 07 — Monorepo Structure
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

AIBAA uses a **monorepo** structure — all packages (frontend, backend, Colab notebooks, shared utilities) live in a single repository. This simplifies:
- Cross-package type sharing
- Unified CI/CD pipeline
- Consistent tooling and dependency management
- Easier local development setup

**Repository Name:** `aibaa`  
**Package Manager:** `pnpm` (frontend) + `pip` (Python)  
**Language:** TypeScript (frontend) + Python 3.11 (backend)

---

## 2. Full Directory Tree

```
aibaa/
│
├── README.md                          # Project overview and quick-start guide
├── .gitignore
├── .env.example                       # Template for environment variables
├── docker-compose.yml                 # Local dev orchestration (optional)
│
├── apps/
│   ├── web/                           # React SPA (Frontend)
│   └── api/                           # FastAPI Orchestration Backend
│
├── packages/
│   ├── shared-types/                  # Shared TypeScript/Python type definitions
│   └── ui-components/                 # Reusable React UI components (design system)
│
├── agents/                            # All AI agent implementations
│   ├── orchestrator/
│   ├── modeling/
│   ├── pitchbook/
│   ├── due_diligence/
│   ├── research/
│   ├── doc_drafter/
│   └── coordination/
│
├── tools/                             # Agent tools (callable functions)
│   ├── file_parser/
│   ├── excel_writer/
│   ├── pdf_generator/
│   ├── doc_generator/
│   ├── python_executor/
│   └── web_search/
│
├── colab/                             # Google Colab notebooks and inference server
│   ├── notebooks/
│   └── inference_server/
│
├── fine_tuning/                       # Unsloth fine-tuning pipeline
│   ├── datasets/
│   ├── training/
│   └── evaluation/
│
├── templates/                         # Output document templates
│   ├── excel/
│   ├── pdf/
│   └── docx/
│
├── tests/                             # Cross-package tests
│   ├── integration/
│   └── e2e/
│
└── docs/                              # All PRE-DEV documentation (this folder)
    ├── 01-product-requirements.md
    ├── 02-user-stories-and-acceptance-criteria.md
    ├── 03-information-architecture.md
    ├── 04-system-architecture.md
    ├── 05-database-schema.md
    ├── 06-api-contracts.md
    ├── 07-monorepo-structure.md
    ├── 08-computation-engine-spec.md
    ├── 09-engineering-scope-definition.md
    ├── 10-development-phases.md
    ├── 11-environment-and-devops.md
    └── 12-testing-strategy.md
```

---

## 3. Detailed Package Breakdown

### `apps/web/` — React SPA

```
apps/web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html
│
├── public/
│   ├── favicon.ico
│   └── assets/
│
└── src/
    ├── main.tsx                       # App entry point
    ├── App.tsx                        # Root component + router
    │
    ├── pages/
    │   ├── Dashboard.tsx
    │   ├── NewDeal.tsx
    │   ├── DealWorkspace.tsx
    │   │   ├── OverviewTab.tsx
    │   │   ├── DocumentsTab.tsx
    │   │   ├── AgentsTab.tsx
    │   │   ├── OutputsTab.tsx
    │   │   └── SettingsTab.tsx
    │   ├── GlobalSettings.tsx
    │   └── Help.tsx
    │
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx
    │   │   ├── TopBar.tsx
    │   │   └── Breadcrumb.tsx
    │   ├── deals/
    │   │   ├── DealCard.tsx
    │   │   ├── DealForm.tsx
    │   │   └── DealStatusBadge.tsx
    │   ├── agents/
    │   │   ├── AgentCard.tsx
    │   │   ├── AgentInputPanel.tsx
    │   │   ├── ReasoningPanel.tsx
    │   │   └── ProgressStream.tsx
    │   ├── documents/
    │   │   ├── DocumentUploadZone.tsx
    │   │   ├── DocumentList.tsx
    │   │   └── DocumentPreview.tsx
    │   ├── outputs/
    │   │   ├── OutputCard.tsx
    │   │   ├── OutputPreview.tsx
    │   │   └── ReviewActions.tsx
    │   ├── tasks/
    │   │   ├── TaskBoard.tsx
    │   │   ├── TaskCard.tsx
    │   │   └── TaskForm.tsx
    │   └── common/
    │       ├── Button.tsx
    │       ├── Modal.tsx
    │       ├── Toast.tsx
    │       ├── Badge.tsx
    │       ├── Spinner.tsx
    │       ├── EmptyState.tsx
    │       └── ErrorBoundary.tsx
    │
    ├── hooks/
    │   ├── useDeals.ts
    │   ├── useAgentRun.ts
    │   ├── useSSEStream.ts
    │   ├── useDocuments.ts
    │   └── useOutputs.ts
    │
    ├── store/
    │   ├── dealStore.ts               # Zustand store for deals
    │   ├── agentStore.ts              # Zustand store for agent state
    │   └── settingsStore.ts           # Zustand store for settings
    │
    ├── api/
    │   ├── client.ts                  # Axios instance + interceptors
    │   ├── deals.ts                   # Deal API functions
    │   ├── documents.ts               # Document API functions
    │   ├── agents.ts                  # Agent API functions
    │   ├── outputs.ts                 # Output API functions
    │   └── settings.ts                # Settings API functions
    │
    ├── types/
    │   └── index.ts                   # TypeScript type definitions
    │
    └── styles/
        ├── globals.css                # CSS reset + base styles
        └── design-tokens.css          # B&W color tokens
```

---

### `apps/api/` — FastAPI Orchestration Backend

```
apps/api/
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Makefile
│
└── src/
    ├── main.py                        # FastAPI app entry point
    ├── config.py                      # Environment config (Pydantic Settings)
    │
    ├── routers/
    │   ├── __init__.py
    │   ├── deals.py
    │   ├── documents.py
    │   ├── agents.py
    │   ├── outputs.py
    │   ├── tasks.py
    │   └── settings.py
    │
    ├── models/
    │   ├── __init__.py
    │   ├── deal.py                    # Pydantic models for Deal
    │   ├── document.py
    │   ├── agent_run.py
    │   ├── output.py
    │   ├── task.py
    │   └── settings.py
    │
    ├── services/
    │   ├── __init__.py
    │   ├── deal_service.py
    │   ├── document_service.py
    │   ├── agent_service.py           # Orchestrates agent execution
    │   ├── output_service.py
    │   └── task_service.py
    │
    ├── store/
    │   ├── __init__.py
    │   └── memory_store.py            # In-memory data store (v1)
    │
    ├── llm/
    │   ├── __init__.py
    │   ├── client.py                  # HTTP client to Colab inference server
    │   └── prompt_builder.py          # Prompt construction per agent type
    │
    └── utils/
        ├── __init__.py
        ├── file_utils.py
        ├── error_handlers.py
        └── logging_config.py
```

---

### `agents/` — Agent Implementations

```
agents/
├── base_agent.py                      # Abstract base class for all agents
│
├── orchestrator/
│   ├── __init__.py
│   ├── agent.py                       # OrchestratorAgent class
│   └── routing_rules.py              # Task routing logic
│
├── modeling/
│   ├── __init__.py
│   ├── agent.py                       # FinancialModelingAgent class
│   ├── dcf.py                         # DCF model logic
│   ├── lbo.py                         # LBO model logic
│   └── comparable_analysis.py         # CCA logic
│
├── pitchbook/
│   ├── __init__.py
│   ├── agent.py                       # PitchbookAgent class
│   ├── slide_builder.py              # Individual slide construction
│   └── pdf_composer.py               # Assembles slides into final PDF
│
├── due_diligence/
│   ├── __init__.py
│   ├── agent.py                       # DueDiligenceAgent class
│   ├── document_classifier.py
│   ├── risk_extractor.py
│   └── checklist_populator.py
│
├── research/
│   ├── __init__.py
│   ├── agent.py                       # ResearchAgent class
│   ├── industry_analyzer.py
│   └── buyer_universe_builder.py
│
├── doc_drafter/
│   ├── __init__.py
│   ├── agent.py                       # DocDrafterAgent class
│   ├── cim_sections.py
│   └── narrative_generator.py
│
└── coordination/
    ├── __init__.py
    ├── agent.py                       # CoordinationAgent class
    ├── note_processor.py
    └── task_extractor.py
```

---

### `tools/` — Agent Tools

```
tools/
├── base_tool.py                       # Abstract Tool base class
│
├── file_parser/
│   ├── __init__.py
│   ├── pdf_parser.py                  # PyMuPDF-based PDF text extraction
│   ├── excel_parser.py                # openpyxl-based XLSX parsing
│   ├── word_parser.py                 # python-docx based DOCX parsing
│   └── csv_parser.py
│
├── excel_writer/
│   ├── __init__.py
│   ├── workbook_builder.py            # Creates XLSX from structured data
│   └── chart_builder.py              # Adds charts to Excel files
│
├── pdf_generator/
│   ├── __init__.py
│   ├── report_builder.py              # ReportLab-based PDF generation
│   └── template_renderer.py          # Applies B&W design templates
│
├── doc_generator/
│   ├── __init__.py
│   └── word_builder.py               # python-docx based DOCX generation
│
├── python_executor/
│   ├── __init__.py
│   └── safe_executor.py               # Sandboxed Python code execution
│
└── web_search/
    ├── __init__.py
    └── search_client.py               # Stub web search (v2: real API)
```

---

### `colab/` — Colab Integration

```
colab/
├── notebooks/
│   ├── 01_environment_setup.ipynb     # Install Unsloth + dependencies
│   ├── 02_load_model.ipynb            # Load base model + LoRA adapters
│   ├── 03_start_inference_server.ipynb # Start FastAPI + ngrok tunnel
│   └── 04_fine_tuning_guide.ipynb    # Step-by-step fine-tuning notebook
│
└── inference_server/
    ├── requirements.txt
    ├── server.py                      # FastAPI inference server (runs in Colab)
    └── model_loader.py               # Unsloth model loading utilities
```

---

### `fine_tuning/` — Unsloth Fine-Tuning Pipeline

```
fine_tuning/
├── datasets/
│   ├── raw/                           # Raw IB training data (CSV/JSONL)
│   ├── processed/                     # Cleaned, formatted datasets
│   └── README.md                      # Dataset documentation
│
├── training/
│   ├── config.yaml                    # Training hyperparameters
│   ├── train.py                       # Unsloth LoRA training script
│   └── prompt_templates.py           # Instruction-tuning prompt formats
│
└── evaluation/
    ├── eval.py                        # Model evaluation script
    ├── benchmarks/                    # IB-specific benchmark tasks
    └── results/                       # Evaluation results (gitignored)
```

---

### `templates/` — Document Templates

```
templates/
├── excel/
│   ├── dcf_template.xlsx             # DCF model skeleton with formatting
│   ├── lbo_template.xlsx             # LBO model skeleton
│   └── cca_template.xlsx             # Comparable company analysis skeleton
│
├── pdf/
│   ├── pitchbook_template.py         # ReportLab template: B&W pitchbook
│   ├── dd_report_template.py         # ReportLab template: DD risk report
│   └── research_brief_template.py    # ReportLab template: research brief
│
└── docx/
    ├── cim_template.docx             # CIM skeleton with styles
    └── executive_summary_template.docx
```

---

## 4. Package Dependencies

### Frontend (`apps/web/package.json`)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "react-dropzone": "^14.2.0",
    "react-pdf": "^7.5.0",
    "@tanstack/react-query": "^5.0.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "typescript": "^5.2.0",
    "tailwindcss": "^3.3.0",
    "@types/react": "^18.2.0",
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0"
  }
}
```

### Backend (`apps/api/requirements.txt`)
```
fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
httpx==0.25.0
python-multipart==0.0.6
PyMuPDF==1.23.0
python-docx==1.1.0
openpyxl==3.1.2
reportlab==4.0.7
pandas==2.1.0
numpy==1.26.0
aiofiles==23.2.1
```

### Colab Inference Server (`colab/inference_server/requirements.txt`)
```
unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git
fastapi==0.104.0
uvicorn==0.24.0
pyngrok==7.0.0
transformers==4.36.0
torch==2.1.0
bitsandbytes==0.41.0
```

---

## 5. Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `agent_service.py` |
| Python classes | `PascalCase` | `FinancialModelingAgent` |
| Python functions | `snake_case` | `build_dcf_model()` |
| TypeScript files | `PascalCase.tsx` / `camelCase.ts` | `AgentCard.tsx`, `useAgentRun.ts` |
| TypeScript components | `PascalCase` | `AgentCard` |
| CSS class names | `kebab-case` | `agent-card__reasoning-panel` |
| API routes | `kebab-case` | `/agent-runs/:id` |
| Environment variables | `SCREAMING_SNAKE_CASE` | `LLM_ENDPOINT_URL` |
| Git branches | `type/description` | `feat/dcf-model-agent` |
| Commit messages | Conventional Commits | `feat: add DCF model output formatter` |

---

*End of Document — 07-monorepo-structure.md*
