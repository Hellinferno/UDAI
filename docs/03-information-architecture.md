# 03 — Information Architecture (IA)
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

This document defines the structural organization of the AIBAA application — the pages, components, navigation hierarchy, content taxonomy, and data flows that constitute the user-facing experience. The IA is designed to be minimal, expert-facing, and optimized for speed-to-output in a financial workflow.

---

## 2. Site Map

```
AIBAA Application
│
├── 🏠 Dashboard (/)
│   ├── Active Deals List
│   ├── Recent Outputs
│   └── Quick Start Panel
│
├── ➕ New Deal (/deals/new)
│   ├── Deal Setup Form
│   └── Document Upload (optional at creation)
│
├── 📁 Deal Workspace (/deals/:dealId)
│   │
│   ├── Overview Tab
│   │   ├── Deal Summary Card
│   │   ├── Task Tracker Board
│   │   └── Activity Log
│   │
│   ├── Documents Tab (/deals/:dealId/documents)
│   │   ├── Upload Zone
│   │   ├── Document List
│   │   └── Document Preview Panel
│   │
│   ├── Agents Tab (/deals/:dealId/agents)
│   │   ├── Financial Modeling Agent
│   │   ├── Pitchbook Agent
│   │   ├── Due Diligence Agent
│   │   ├── Market Research Agent
│   │   ├── Deal Documentation Agent
│   │   └── Deal Coordination Agent
│   │
│   ├── Outputs Tab (/deals/:dealId/outputs)
│   │   ├── Generated Files List
│   │   ├── In-browser Preview
│   │   └── Download / Share
│   │
│   └── Settings Tab (/deals/:dealId/settings)
│       ├── Deal Configuration
│       ├── Agent Behavior Settings
│       └── Disclaimer & Compliance Notes
│
├── ⚙️ Global Settings (/settings)
│   ├── LLM Backend Configuration (Colab Endpoint URL)
│   ├── Default Preferences
│   └── Export Format Preferences
│
└── ❓ Help (/help)
    ├── Agent Capability Guide
    ├── Input Format Instructions
    └── FAQ
```

---

## 3. Navigation Model

### Primary Navigation (Left Sidebar)
| Icon | Label | Route |
|---|---|---|
| 🏠 | Dashboard | `/` |
| 📁 | Deals | `/deals` |
| ⚙️ | Settings | `/settings` |
| ❓ | Help | `/help` |

### Contextual Navigation (Deal Workspace — Top Tabs)
| Tab | Purpose |
|---|---|
| Overview | High-level deal status and task board |
| Documents | Data room / document upload and viewer |
| Agents | Trigger and configure each AI agent |
| Outputs | All generated files and previews |
| Settings | Deal-specific configuration |

### Breadcrumb Structure
```
Dashboard > Deal Name > [Active Tab]
e.g., Dashboard > Nexus Pharma Acquisition > Agents > Financial Modeling
```

---

## 4. Page-Level Content Inventory

### 4.1 Dashboard (`/`)

| Component | Content | Source |
|---|---|---|
| Header | "AIBAA" wordmark + user greeting | Static / Auth |
| Deal Cards | Deal name, type, status, last modified | Deal Store |
| Quick Stats | # Active Deals, # Outputs Generated, # Pending Reviews | Aggregated |
| New Deal CTA | Prominent black button: "+ New Deal" | UI Action |
| Recent Activity Feed | Last 5 agent actions across all deals | Event Log |

---

### 4.2 New Deal Form (`/deals/new`)

| Field | Type | Validation |
|---|---|---|
| Deal Name | Text input | Required, max 80 chars |
| Company Name | Text input | Required, max 80 chars |
| Deal Type | Dropdown: M&A / IPO / Fundraising / Restructuring / Other | Required |
| Industry | Dropdown (20+ sectors) | Required |
| Deal Stage | Dropdown: Preliminary / Active / Final | Required |
| Notes / Context | Textarea | Optional, max 500 chars |

---

### 4.3 Deal Workspace — Agents Tab (`/deals/:dealId/agents`)

Each agent card contains:
- **Agent Name** (e.g., "Financial Modeling Agent")
- **Description** (one-line capability summary)
- **Status Badge** (Idle / Running / Completed / Error)
- **Input Panel** (context-sensitive: text prompt, file selector, parameters)
- **Run Button** (triggers API call to Colab backend)
- **Reasoning Panel** (collapsible: shows chain-of-thought steps)
- **Output Preview** (inline text or file link)

---

### 4.4 Outputs Tab (`/deals/:dealId/outputs`)

| Column | Content |
|---|---|
| File Name | e.g., "NexusPharma_DCF_Model_v1.xlsx" |
| Agent | Which agent generated it |
| Type | XLSX / PDF / DOCX / MD |
| Generated At | Timestamp |
| Status | Draft / Approved / Archived |
| Actions | Preview / Download / Approve / Request Revision |

---

## 5. Content Taxonomy

### 5.1 Deal Type Taxonomy
```
├── Mergers & Acquisitions (M&A)
│   ├── Buy-Side Advisory
│   └── Sell-Side Advisory
├── Capital Markets
│   ├── IPO
│   ├── Secondary Offering
│   └── Debt Raise
├── Private Equity
│   ├── LBO
│   └── Growth Equity
├── Restructuring
│   ├── In-Court
│   └── Out-of-Court
└── Other
```

### 5.2 Document Type Taxonomy (Data Room)
```
├── Financial Statements
│   ├── Income Statement
│   ├── Balance Sheet
│   └── Cash Flow Statement
├── Corporate Documents
│   ├── Certificate of Incorporation
│   ├── Cap Table
│   └── Shareholder Agreements
├── Contracts
│   ├── Customer Contracts
│   ├── Supplier Agreements
│   └── Employment Agreements
├── Tax Documents
│   ├── Tax Returns (3-yr)
│   └── Tax Schedules
├── Legal
│   ├── IP Registrations
│   ├── Litigation History
│   └── Regulatory Filings
└── Operational
    ├── Org Chart
    ├── Product/Service Overview
    └── Customer List
```

### 5.3 Agent Output Type Taxonomy
```
├── Financial Models
│   ├── DCF Model (.xlsx)
│   ├── LBO Model (.xlsx)
│   └── Comparable Company Analysis (.xlsx)
├── Presentations
│   └── Pitchbook (.pdf / .pptx)
├── Due Diligence Reports
│   ├── Risk Summary (.pdf)
│   └── DD Checklist (.xlsx)
├── Research Briefs
│   ├── Industry Overview (.pdf)
│   └── Buyer/Target Universe (.pdf / .xlsx)
├── Deal Documents
│   ├── CIM Draft (.docx / .pdf)
│   ├── Executive Summary (.docx)
│   └── Deal Teaser (.pdf)
└── Coordination Artifacts
    ├── Meeting Summary (.md / .pdf)
    └── Deal Task Tracker (.md / .xlsx)
```

---

## 6. User Flow Diagrams

### Flow 1: First-Time User Starting a Deal
```
Land on Dashboard
→ Click "+ New Deal"
→ Fill Deal Setup Form
→ Upload Documents (optional)
→ Redirected to Deal Workspace → Overview Tab
→ Click "Agents" tab
→ Select "Financial Modeling Agent"
→ Input deal parameters
→ Click "Run Agent"
→ Watch Reasoning Panel update
→ Output file appears in Outputs tab
→ Preview → Approve → Download
```

### Flow 2: Due Diligence Workflow
```
Open Deal Workspace → Documents Tab
→ Upload data room (bulk upload)
→ Navigate to Agents Tab → Due Diligence Agent
→ Click "Run Due Diligence"
→ Agent processes each document
→ Risk Report generated → Outputs Tab
→ Review flags → Mark as Reviewed / Escalate
→ DD Checklist auto-populated
→ Download final Risk Report as PDF
```

### Flow 3: Pitchbook Generation
```
Open Deal Workspace → Agents Tab → Pitchbook Agent
→ Enter deal brief text (or auto-pulled from deal context)
→ Set Pitchbook Settings: purpose, tone, slides to include
→ Click "Generate Pitchbook"
→ Progress bar: "Slide 1 of 12…"
→ In-browser PDF preview opens
→ Review each slide
→ Request revision on any slide
→ Final approval → Download PDF
```

---

## 7. Empty States

| Screen | Empty State Message |
|---|---|
| Dashboard (no deals) | "No deals yet. Create your first deal to get started." + CTA button |
| Documents Tab (no uploads) | "No documents uploaded. Drag and drop files here or click to browse." |
| Outputs Tab (no outputs) | "No outputs generated yet. Head to the Agents tab to run your first analysis." |
| Task Tracker (no tasks) | "No tasks yet. Tasks are created automatically when agents run." |

---

## 8. Error States

| Scenario | Error Message |
|---|---|
| Colab backend unreachable | "Agent backend is offline. Please ensure your Colab session is running and the endpoint URL is configured in Settings." |
| File parse failure | "We couldn't read this file. Please check the format and try again." |
| Agent timeout (>5 min) | "The agent is taking longer than expected. It will continue in the background." |
| Hallucination guard trigger | "⚠️ Numbers in this output could not be verified against source documents. Human review required." |

---

*End of Document — 03-information-architecture.md*
