# 02 — User Stories & Acceptance Criteria
## AI Investment Banking Analyst Agent (AIBAA)

---

## Format Convention

Each story follows:
```
AS A [persona]
I WANT TO [action]
SO THAT [benefit]
```

Acceptance Criteria (AC) follow the **Given / When / Then** format.

Priority Levels: `P0` = Must-Have (MVP) | `P1` = Should-Have | `P2` = Nice-to-Have

---

## Epic 1: Onboarding & Deal Setup

---

### US-001 — Create a New Deal
**Priority:** P0

> As an **Independent Sponsor**,  
> I want to create a new deal workspace by entering a company name and deal type,  
> so that all subsequent agent outputs are organized under this deal.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I am on the dashboard | I click "New Deal" | A modal appears asking for Deal Name, Company Name, Deal Type (M&A / IPO / Fundraising / Other), and Industry |
| AC-2 | I have filled all required fields | I click "Create Deal" | A new deal workspace is created and I am redirected to its overview page |
| AC-3 | I leave "Company Name" blank | I click "Create Deal" | An inline validation error appears: "Company Name is required" |
| AC-4 | Deal is created | I view the dashboard | The new deal appears in the deal list with status "Active" and creation timestamp |

---

### US-002 — Upload Supporting Documents
**Priority:** P0

> As a **Boutique IB Associate**,  
> I want to upload financial statements and company documents to a deal,  
> so that the AI agents can analyze them as part of their work.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I am inside a deal workspace | I click "Upload Files" | A file picker opens accepting .pdf, .docx, .xlsx, .csv |
| AC-2 | I upload a file under 50MB | Upload completes | A success toast appears and the file is listed under "Deal Documents" |
| AC-3 | I upload a file over 50MB | Upload is attempted | An error message states: "File exceeds 50MB limit" |
| AC-4 | I upload an unsupported file type (.jpg) | Upload is attempted | An error message states: "Unsupported file type" |
| AC-5 | Files are uploaded | I view document list | Each file shows name, type, upload timestamp, and size |

---

## Epic 2: Financial Modeling

---

### US-003 — Generate a DCF Model
**Priority:** P0

> As an **Independent Sponsor**,  
> I want to describe a target company and upload its financials,  
> so that the AI builds a Discounted Cash Flow model I can download.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I have uploaded a financial Excel file | I click "Build DCF Model" | The system acknowledges receipt and begins processing |
| AC-2 | Processing is complete | The model finishes | A downloadable .xlsx file appears in "Outputs" with DCF, assumptions, and sensitivity tabs |
| AC-3 | I open the Excel output | I check the DCF tab | The model contains: revenue projections (5-yr), EBITDA margin, WACC inputs, terminal value, and implied share price range |
| AC-4 | The model is generated | I check the assumptions tab | All key assumptions are clearly labeled and sourced from the uploaded financials |
| AC-5 | No financials are uploaded | I request a DCF | The system prompts: "Please upload financial statements to continue" |

---

### US-004 — Generate an LBO Model
**Priority:** P1

> As a **Financial Consultant**,  
> I want to generate an LBO model by inputting acquisition price and debt structure,  
> so that I can evaluate private equity return scenarios.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I enter acquisition price, debt/equity split, target hold period | I click "Build LBO" | The agent generates an LBO model with entry/exit multiples, IRR, and MOIC |
| AC-2 | Model is complete | I download the output | .xlsx contains: Sources & Uses, Income Statement (projected), Debt Schedule, Returns Summary |
| AC-3 | I change the hold period from 5 to 7 years | I regenerate | The model recalculates and IRR/MOIC update accordingly |

---

### US-005 — Comparable Company Analysis (CCA)
**Priority:** P1

> As a **Family Office Analyst**,  
> I want the system to identify comparable public companies and pull their trading multiples,  
> so that I can benchmark a target company's valuation.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I provide a company name and industry | I request CCA | The agent returns a table of 5–10 comparable companies with EV/EBITDA, P/E, EV/Revenue |
| AC-2 | CCA is generated | I download output | .xlsx contains a formatted comps table with median/mean benchmarks highlighted |
| AC-3 | No comparable found | Agent cannot identify peers | System notifies: "Low confidence on comparables — please review suggestions" and still outputs best-effort result |

---

## Epic 3: Pitchbook Generation

---

### US-006 — Generate a Full Pitchbook
**Priority:** P0

> As a **Boutique IB Associate**,  
> I want to input a deal brief and have the AI generate a full pitchbook PDF,  
> so that I can present to a client within hours instead of days.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I have an active deal with uploaded docs | I click "Generate Pitchbook" | The agent asks: "What is the purpose of this pitchbook? (e.g., sell-side, buy-side, capital raise)" |
| AC-2 | I confirm the purpose | Processing begins | The system displays a progress indicator with current step (e.g., "Building slide 3 of 12…") |
| AC-3 | Generation is complete | I open the preview | A PDF preview renders in-browser with a black-and-white professional theme |
| AC-4 | I review the pitchbook | I click "Download" | A well-formatted .pdf is downloaded to my device |
| AC-5 | I dislike slide 4 | I click "Revise Slide" and provide a note | The agent regenerates that slide only and updates the document |

---

### US-007 — Customize Pitchbook Tone and Structure
**Priority:** P1

> As a **Financial Consultant**,  
> I want to specify the tone (conservative vs. aggressive) and required slide types,  
> so that the pitchbook matches my client's preferences.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | Before generating | I open "Pitchbook Settings" | I can select: tone (conservative / balanced / aggressive), include/exclude slide types |
| AC-2 | I exclude "Market Overview" slide | I generate | The pitchbook does not include that section |
| AC-3 | I select "aggressive" tone | I generate | The narrative uses stronger deal rationale language and higher valuation multiples |

---

## Epic 4: Due Diligence

---

### US-008 — Run Due Diligence on Uploaded Documents
**Priority:** P0

> As an **Independent Sponsor**,  
> I want to upload a data room bundle and receive a due diligence risk report,  
> so that I can identify red flags before making an offer.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I have uploaded 5+ documents | I click "Run Due Diligence" | The agent begins processing each document sequentially |
| AC-2 | Analysis is complete | I view the report | I see a categorized report: Financial Risks, Legal Risks, Operational Risks, with severity ratings (High/Medium/Low) |
| AC-3 | A red flag is detected | I click on it | The agent shows the exact document, page, and quote that triggered the flag |
| AC-4 | I want to dismiss a flag | I click "Mark as Reviewed" | The flag is archived with a timestamp and my note |
| AC-5 | No documents uploaded | I click "Run DD" | System blocks action: "Please upload documents to the data room first" |

---

### US-009 — DD Checklist Completion Tracking
**Priority:** P1

> As a **Boutique IB Associate**,  
> I want a standard DD checklist pre-populated by the agent,  
> so that I can track which items have been reviewed vs. outstanding.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | DD is initiated | Checklist loads | A standard IB DD checklist is shown (Financial Statements, Cap Table, Material Contracts, IP, Tax, etc.) |
| AC-2 | The agent finds a document matching an item | It auto-ticks the checklist | The item shows "Reviewed by AI" with confidence score |
| AC-3 | An item is missing | Agent cannot find matching doc | The item is flagged "Missing — Not Found in Data Room" in red |

---

## Epic 5: Market Research

---

### US-010 — Generate Industry Research Brief
**Priority:** P0

> As a **Financial Consultant**,  
> I want to enter an industry sector and receive a structured research brief,  
> so that I can quickly understand market context for a client meeting.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I enter "SaaS – HR Technology" | I click "Research Industry" | The agent produces a brief covering: market size, growth rate, key players, tailwinds/headwinds, recent M&A activity |
| AC-2 | Research is complete | I download the brief | A .pdf is generated with section headers and a consistent black-and-white visual style |
| AC-3 | I request a buyer universe | I click "Identify Strategic Buyers" | The agent returns a list of 10–15 potential acquirers with rationale per buyer |

---

## Epic 6: Deal Documentation

---

### US-011 — Draft a CIM (Confidential Information Memorandum)
**Priority:** P0

> As a **Boutique IB Associate**,  
> I want the AI to draft the market overview and financial summary sections of a CIM,  
> so that I have a strong first draft in under an hour.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I provide a deal brief + uploaded financials | I click "Draft CIM" | The agent outputs a structured Word/PDF document with: Executive Summary, Business Overview, Market Overview, Financial Summary |
| AC-2 | I review the Financial Summary | Numbers must match | All figures in the narrative match the uploaded financials (no hallucinated numbers) |
| AC-3 | I want to edit a section inline | I click "Edit Section" | A text editor opens pre-populated with the AI-generated text for that section only |

---

## Epic 7: Deal Coordination

---

### US-012 — Capture and Summarize Meeting Notes
**Priority:** P1

> As an **Independent Sponsor**,  
> I want to paste raw meeting notes and receive a structured summary with action items,  
> so that nothing falls through the cracks after a client call.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I paste unstructured notes | I click "Process Notes" | The agent outputs: Summary, Key Decisions, Action Items (with owner + deadline if mentioned), Open Questions |
| AC-2 | An action item has a deadline | It is in the notes | The action item appears in the Deal Tracker automatically |
| AC-3 | I approve the summary | I click "Save to Deal" | The summary is saved to the deal's activity log |

---

### US-013 — Deal Status Tracker
**Priority:** P1

> As a **Boutique IB Associate**,  
> I want a live task board for my active deal,  
> so that I always know what is outstanding and what is done.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I open a deal workspace | Tracker is visible | I see tasks grouped by: To Do / In Progress / Completed |
| AC-2 | Agent generates an output | Task auto-updates | The corresponding task moves to "Completed" with a link to the output file |
| AC-3 | I manually add a task | I type and press Enter | A new task card appears in "To Do" |

---

## Epic 8: UI and UX

---

### US-014 — Professional Black-and-White Interface
**Priority:** P0

> As any user,  
> I want the entire application to use a professional black-and-white color system,  
> so that it feels appropriate for a financial services context.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | I load the app | Page renders | Primary background is white (#FFFFFF), primary text is black (#0A0A0A), accents are mid-grey (#6B6B6B) |
| AC-2 | I hover over a button | I see feedback | Buttons use black fill with white text on hover; border transitions are smooth |
| AC-3 | I view a generated PDF | It opens in browser | The PDF uses the same black-and-white design system (no color charts) |
| AC-4 | I use the app on a 13" laptop | No scroll or clipping | The layout is fully responsive at 1280px minimum width |

---

### US-015 — Agent Transparency (Reasoning Display)
**Priority:** P1

> As any user,  
> I want to see the agent's reasoning steps before the final output is shown,  
> so that I trust and understand what it produced.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|---|---|---|
| AC-1 | An agent task is running | I watch the UI | I see a "Thinking…" panel with real-time steps (e.g., "Parsing income statement…", "Applying DCF formula…") |
| AC-2 | Task completes | Reasoning is available | I can expand a "How was this created?" section under any output |
| AC-3 | Agent is unsure | Confidence is low | A yellow warning badge appears: "Low confidence — human review recommended" |

---

*End of Document — 02-user-stories-and-acceptance-criteria.md*
