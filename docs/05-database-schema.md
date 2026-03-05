# 05 — Database Schema
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

**v1 Storage Strategy:** In-memory Python dicts + local filesystem (no persistent DB in MVP).  
**v2 Target:** SQLite (local) or Supabase (PostgreSQL) for persistence.  
**v3 Target:** Full PostgreSQL + Redis for caching + vector store for semantic memory.

This document defines the canonical data model that will be used across all storage backends. All schemas are written in SQL-compatible notation for portability.

---

## 2. Entity Relationship Diagram

```
┌─────────────┐       ┌───────────────┐       ┌──────────────────┐
│    deals    │──1:N──│   documents   │       │   agent_runs     │
└─────────────┘       └───────────────┘       └──────────────────┘
       │                                              │
       │──1:N──────────────────────────────────────▶─┘
       │
       │──1:N──┌───────────────┐
               │    outputs    │
               └───────────────┘
       │
       │──1:N──┌───────────────┐
               │     tasks     │
               └───────────────┘
       │
       │──1:N──┌─────────────────┐
               │  activity_logs  │
               └─────────────────┘
```

---

## 3. Table Definitions

### 3.1 `deals`

The root entity. Every piece of work belongs to a deal.

```sql
CREATE TABLE deals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(80)  NOT NULL,
    company_name    VARCHAR(80)  NOT NULL,
    deal_type       VARCHAR(30)  NOT NULL CHECK (deal_type IN (
                        'ma_buyside', 'ma_sellside', 'ipo',
                        'secondary_offering', 'debt_raise',
                        'lbo', 'growth_equity', 'restructuring', 'other'
                    )),
    industry        VARCHAR(60)  NOT NULL,
    deal_stage      VARCHAR(20)  NOT NULL DEFAULT 'preliminary' CHECK (deal_stage IN (
                        'preliminary', 'active', 'final', 'closed', 'dead'
                    )),
    notes           TEXT,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    is_archived     BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_deals_deal_type    ON deals (deal_type);
CREATE INDEX idx_deals_deal_stage   ON deals (deal_stage);
CREATE INDEX idx_deals_created_at   ON deals (created_at DESC);
```

**Field Notes:**
- `id`: UUID v4, used as primary key throughout.
- `deal_type`: Enum-constrained, maps to taxonomy in IA doc.
- `deal_stage`: Tracks where the deal is in lifecycle.

---

### 3.2 `documents`

Files uploaded to the deal's virtual data room.

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID         NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    filename        VARCHAR(255) NOT NULL,
    original_name   VARCHAR(255) NOT NULL,
    file_type       VARCHAR(10)  NOT NULL CHECK (file_type IN (
                        'pdf', 'docx', 'xlsx', 'csv', 'txt'
                    )),
    file_size_bytes BIGINT       NOT NULL,
    storage_path    TEXT         NOT NULL,        -- local path or S3 key
    doc_category    VARCHAR(50),                  -- 'financial', 'legal', 'corporate', 'tax', 'operational'
    parsed_text     TEXT,                         -- extracted plain text for LLM context
    parse_status    VARCHAR(20)  NOT NULL DEFAULT 'pending' CHECK (parse_status IN (
                        'pending', 'processing', 'completed', 'failed'
                    )),
    parse_error     TEXT,
    uploaded_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_deal_id      ON documents (deal_id);
CREATE INDEX idx_documents_doc_category ON documents (doc_category);
CREATE INDEX idx_documents_parse_status ON documents (parse_status);
```

**Field Notes:**
- `parsed_text`: Extracted text stored for use in LLM context window.
- `doc_category`: Manually set or auto-classified by an agent on upload.
- `storage_path`: In v1 = local filesystem path; v2 = S3 key.

---

### 3.3 `agent_runs`

Immutable log of every agent task execution.

```sql
CREATE TABLE agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID         NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    agent_type      VARCHAR(30)  NOT NULL CHECK (agent_type IN (
                        'orchestrator', 'modeling', 'pitchbook',
                        'due_diligence', 'research', 'doc_drafter', 'coordination'
                    )),
    task_name       VARCHAR(100) NOT NULL,                  -- e.g., 'dcf_model', 'full_pitchbook'
    status          VARCHAR(20)  NOT NULL DEFAULT 'queued' CHECK (status IN (
                        'queued', 'running', 'completed', 'failed', 'cancelled'
                    )),
    input_payload   JSONB        NOT NULL DEFAULT '{}',     -- parameters sent to agent
    llm_prompt      TEXT,                                   -- full prompt sent to LLM
    llm_response    TEXT,                                   -- raw LLM response
    reasoning_steps JSONB        NOT NULL DEFAULT '[]',     -- chain-of-thought steps
    confidence_score FLOAT,                                 -- 0.0–1.0
    error_message   TEXT,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_runs_deal_id    ON agent_runs (deal_id);
CREATE INDEX idx_agent_runs_status     ON agent_runs (status);
CREATE INDEX idx_agent_runs_agent_type ON agent_runs (agent_type);
CREATE INDEX idx_agent_runs_created_at ON agent_runs (created_at DESC);
```

**Field Notes:**
- `reasoning_steps`: Array of objects like `[{"step": 1, "thought": "...", "action": "...", "observation": "..."}]`
- `confidence_score`: Derived from LLM output, used for hallucination warning badges.
- `input_payload`: Stored for reproducibility and audit.

---

### 3.4 `outputs`

Generated files from agent runs.

```sql
CREATE TABLE outputs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID         NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    agent_run_id    UUID         NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    filename        VARCHAR(255) NOT NULL,
    output_type     VARCHAR(10)  NOT NULL CHECK (output_type IN (
                        'xlsx', 'pdf', 'docx', 'pptx', 'md', 'json'
                    )),
    output_category VARCHAR(50)  NOT NULL CHECK (output_category IN (
                        'financial_model', 'pitchbook', 'dd_report',
                        'research_brief', 'deal_document', 'task_tracker', 'other'
                    )),
    storage_path    TEXT         NOT NULL,
    file_size_bytes BIGINT,
    review_status   VARCHAR(20)  NOT NULL DEFAULT 'draft' CHECK (review_status IN (
                        'draft', 'approved', 'revision_requested', 'archived'
                    )),
    reviewer_notes  TEXT,
    version         INT          NOT NULL DEFAULT 1,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outputs_deal_id       ON outputs (deal_id);
CREATE INDEX idx_outputs_review_status ON outputs (review_status);
CREATE INDEX idx_outputs_output_type   ON outputs (output_type);
```

**Field Notes:**
- `version`: Increments each time an output is regenerated for the same agent/task.
- `review_status`: Drives the approval workflow in the UI.

---

### 3.5 `tasks`

Deal coordination task tracker (auto-created by agents + manually added by user).

```sql
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID         NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    agent_run_id    UUID         REFERENCES agent_runs(id) ON DELETE SET NULL, -- NULL if manually created
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    owner           VARCHAR(100),                          -- free text (name or "AI Agent")
    status          VARCHAR(20)  NOT NULL DEFAULT 'todo' CHECK (status IN (
                        'todo', 'in_progress', 'completed', 'blocked', 'cancelled'
                    )),
    priority        VARCHAR(10)  NOT NULL DEFAULT 'medium' CHECK (priority IN (
                        'low', 'medium', 'high', 'critical'
                    )),
    due_date        DATE,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    is_ai_generated BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_tasks_deal_id  ON tasks (deal_id);
CREATE INDEX idx_tasks_status   ON tasks (status);
CREATE INDEX idx_tasks_due_date ON tasks (due_date);
```

---

### 3.6 `activity_logs`

Immutable audit trail of all system events.

```sql
CREATE TABLE activity_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID         REFERENCES deals(id) ON DELETE CASCADE,
    event_type      VARCHAR(50)  NOT NULL,          -- e.g., 'document_uploaded', 'agent_completed', 'output_approved'
    entity_type     VARCHAR(30),                    -- 'deal', 'document', 'agent_run', 'output', 'task'
    entity_id       UUID,
    description     TEXT         NOT NULL,
    metadata        JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_logs_deal_id     ON activity_logs (deal_id);
CREATE INDEX idx_activity_logs_event_type  ON activity_logs (event_type);
CREATE INDEX idx_activity_logs_created_at  ON activity_logs (created_at DESC);
```

---

### 3.7 `settings`

User/system configuration.

```sql
CREATE TABLE settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           TEXT         NOT NULL,
    value_type      VARCHAR(20)  NOT NULL DEFAULT 'string' CHECK (value_type IN (
                        'string', 'integer', 'float', 'boolean', 'json'
                    )),
    description     TEXT,
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Seed data
INSERT INTO settings (key, value, value_type, description) VALUES
    ('llm_endpoint_url',     'http://localhost:8001/generate', 'string',  'Colab LLM inference server URL'),
    ('llm_model_name',       'llama3-8b-ib-analyst',          'string',  'Model name loaded in Colab'),
    ('llm_max_tokens',       '4096',                          'integer', 'Max tokens per LLM completion'),
    ('llm_temperature',      '0.2',                           'float',   'LLM temperature (lower = more deterministic)'),
    ('output_pdf_theme',     'black_white',                   'string',  'Color theme for generated PDFs'),
    ('hallucination_guard',  'true',                          'boolean', 'Enable numerical verification step'),
    ('default_deal_stage',   'preliminary',                   'string',  'Default stage for new deals'),
    ('max_upload_size_mb',   '50',                            'integer', 'Maximum file upload size in MB');
```

---

## 4. In-Memory Data Model (v1 Python Implementation)

For v1 (session-based), the above schema maps to Python dataclasses:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

@dataclass
class Deal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    company_name: str = ""
    deal_type: str = "other"
    industry: str = ""
    deal_stage: str = "preliminary"
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    documents: List["Document"] = field(default_factory=list)
    agent_runs: List["AgentRun"] = field(default_factory=list)
    outputs: List["Output"] = field(default_factory=list)
    tasks: List["Task"] = field(default_factory=list)

@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    filename: str = ""
    file_type: str = ""
    file_size_bytes: int = 0
    storage_path: str = ""
    doc_category: Optional[str] = None
    parsed_text: Optional[str] = None
    parse_status: str = "pending"
    uploaded_at: datetime = field(default_factory=datetime.now)

@dataclass
class AgentRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    agent_type: str = ""
    task_name: str = ""
    status: str = "queued"
    input_payload: Dict[str, Any] = field(default_factory=dict)
    reasoning_steps: List[Dict] = field(default_factory=list)
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Output:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    agent_run_id: str = ""
    filename: str = ""
    output_type: str = ""
    output_category: str = ""
    storage_path: str = ""
    review_status: str = "draft"
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    title: str = ""
    status: str = "todo"
    priority: str = "medium"
    owner: str = "AI Agent"
    is_ai_generated: bool = True
    created_at: datetime = field(default_factory=datetime.now)
```

---

## 5. Data Retention Policy

| Data Type | v1 Policy | v2 Policy |
|---|---|---|
| Deal metadata | Session lifetime | Persistent until deleted |
| Uploaded documents | Session lifetime | 90 days + user-controlled delete |
| Generated outputs | Session lifetime | Persistent until deleted |
| Agent run logs | Session lifetime | Permanent (audit trail) |
| LLM prompts/responses | Session lifetime | Encrypted, 30-day retention |

---

*End of Document — 05-database-schema.md*
