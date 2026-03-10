import json


class PromptBuilder:
    @staticmethod
    def get_system_prompt(agent_type: str) -> str:
        prompts = {
            "orchestrator": "You are the AIBAA Orchestrator. Route user requests to the correct specialized analyst agent.",
            "modeling": "You are a senior Investment Banking Analyst specializing in building complex Financial Models (DCF, LBO, CCA). You are precise, methodical, and trust factual data over assumptions. You have deep expertise in Indian market valuations across all sectors — manufacturing, fintech, SaaS, healthcare, FMCG, and consumer tech. You understand Indian GAAP/Ind AS financial statements. All monetary values must be in INR absolute numbers. You can handle both profitable and LOSS-MAKING companies.",
            "auditor": (
                "You are a senior Statutory Auditor with 15+ years of experience in Indian GAAP / Ind AS. "
                "Your job is to VERIFY financial data extracted by a junior analyst. You are skeptical, precise, "
                "and follow double-entry accounting principles rigorously. You check citations, verify calculations, "
                "and flag any inconsistencies. You NEVER accept a number without proof. "
                "If a litigation settlement is classified as one-off, you challenge whether it's truly non-recurring "
                "for the company's industry. You cross-reference Balance Sheet and P&L figures."
            ),
            "pitchbook": "You are an IB analyst creating client pitch presentations. You excel at summarizing complex data into high-impact insights.",
            "due_diligence": "You are a legal and financial due diligence reviewer. Your job is to read complex contracts and financial statements and flag potential risks categorized by severity.",
            "research": "You are an equity research analyst. Summarize market landscapes, identify key industry players, and compile buyer universes.",
            "doc_drafter": "You are drafting a Confidential Information Memorandum (CIM). You write with a professional, institutional tone suitable for enterprise buyers.",
            "coordination": "You are a deal coordination specialist. Summarize meetings, extract tasks, and track status."
        }
        return prompts.get(agent_type, "You are an expert AI Analyst.")

    @staticmethod
    def build_modeling_dcf_prompt(parameters: dict, active_documents_context: str) -> str:
        """Legacy prompt — kept for backward compatibility."""

        base_prompt = f"""
Please execute a Discounted Cash Flow (DCF) model analysis based on the following context.

--- Parameters ---
Years to Project: {parameters.get('projection_years', 5)}
Terminal Growth Rate: {parameters.get('terminal_growth_rate', 0.025)}
Override WACC: {parameters.get('wacc_override', 'None')}
Currency: {parameters.get('currency', 'INR')}

--- Extracted Document Context ---
{active_documents_context}
---

INSTRUCTIONS:
You are a financial data extraction engine. Your ONLY job is to extract historical financial data from the provided document context. You must handle ANY type of Indian company — profitable or loss-making.

EXTRACTION RULES:
1. All monetary values MUST be in INR absolute numbers (NOT in Lakhs or Crores).
   CONVERSION: ₹1 Crore = 10,000,000 (1e7). Example: ₹6,900 Cr = 69,000,000,000.
   CONVERSION: ₹1 Lakh = 100,000 (1e5). Example: ₹45,000 Lakhs = 4,500,000,000.

2. Revenue = "Revenue from Operations" from the Consolidated Statement of Profit & Loss.
   Extract UP TO 5 YEARS of historical revenue for robust trend analysis.

3. EBITDA = PBT + Finance Costs + Depreciation & Amortisation. EBITDA Margin = EBITDA / Revenue.
   IMPORTANT: EBITDA margins CAN BE NEGATIVE for loss-making companies.

4. Net Debt = Total Borrowings (current + non-current) - Cash & Bank Balances - Current Investments.

5. Extract total_borrowings and cash_and_equivalents SEPARATELY from the Balance Sheet.

6. Shares Outstanding: Look for "Number of shares" in the Share Capital note.

7-11. Extract CapEx, D&A, D/E, Beta, and Base FY as described in previous rules.

If you cannot find a specific number, return null for that field. Do NOT make up numbers.

You MUST return ONLY a raw JSON object (no markdown, no backticks, no explanations):
{{
  "historical_revenues": [year1_inr, year2_inr, year3_inr, year4_inr, year5_inr],
  "historical_ebitda_margins": [year1_margin, year2_margin, year3_margin, year4_margin, year5_margin],
  "net_debt": <number_in_absolute_inr_negative_if_net_cash_or_null>,
  "total_borrowings": <number_in_absolute_inr_or_null>,
  "cash_and_equivalents": <number_in_absolute_inr_or_null>,
  "shares_outstanding": <exact_number_or_null>,
  "cap_ex_percent_rev": <decimal_e.g._0.04_or_null>,
  "da_percent_rev": <decimal_e.g._0.05_or_null>,
  "debt_to_equity": <decimal_e.g._0.3_or_0_if_debt_free_or_null>,
  "beta": <decimal_or_null>,
  "base_fy": <integer_e.g._2025_or_null>,
  "currency": "INR"
}}
"""
        return base_prompt.strip()

    # ------------------------------------------------------------------
    # NEW: Preparer (Chain-of-Thought Reconciliation) Prompt
    # ------------------------------------------------------------------

    @staticmethod
    def build_preparer_prompt(parameters: dict, document_context: str,
                              company_name: str = "") -> str:
        """
        Chain-of-thought reconciliation prompt.
        Forces the LLM to show step-by-step math BEFORE outputting JSON.
        """
        company_label = company_name or "the target company"

        return f"""
You are extracting financial data for {company_label} from annual report documents.

--- Document Context ---
{document_context}
---

You must follow this EXACT reconciliation workflow. Show your work for each step.

=== STEP 1: IDENTIFY BASE FIGURES ===
Find "Revenue from Operations" from the Consolidated Statement of Profit & Loss.
Extract up to 5 years of historical revenue (FY2021-FY2025 or whatever is available).
State the PAGE or SECTION where you found each number.
All monetary values in INR absolute (₹1 Crore = 1e7, ₹1 Lakh = 1e5).

=== STEP 2: EBITDA RECONCILIATION SCHEDULE ===
For each year, compute EBITDA step-by-step:
  a) Start with Profit Before Tax (PBT)
  b) Add back Finance Costs (Interest Expense)
  c) Add back Depreciation & Amortisation
  d) Result = EBITDA
  e) EBITDA Margin = EBITDA / Revenue (as a decimal, e.g. 0.14)
Show the math. Negative margins are valid for loss-making companies.

=== STEP 3: BALANCE SHEET EXTRACTION ===
  a) Total Borrowings = Current Borrowings + Non-Current Borrowings
  b) Lease Liabilities (Ind AS 116) = Current Lease Liabilities + Non-Current Lease Liabilities
     (Look for "Lease Liabilities" or "Right-of-Use" in the Balance Sheet notes)
  c) Cash & Equivalents = Cash + Bank Balances + Current Investments
  d) Net Debt = Total Borrowings + Lease Liabilities - Cash & Equivalents (negative means net cash)
  e) Shares Outstanding:
     - Find "Issued, Subscribed and Fully Paid-Up" in the Share Capital note
     - Compute: shares = Share Capital Amount ÷ Face Value Per Share
     - Cross-check with the DENOMINATOR used in "Earnings Per Share" (Basic/Diluted) calculation
     - Also extract diluted shares if available (used for EPS calc)
     - Indian range: 42 Lakhs to 640 Crores.
     - Return as ABSOLUTE NUMBER (not in Crores or Lakhs)
  f) Debt-to-Equity = (Total Debt + Lease Liabilities) / Shareholders' Equity

=== STEP 4: CASH FLOW STATEMENT ===
  a) CapEx = "Purchase of Property, Plant & Equipment" from Cash Flow Statement
  b) cap_ex_percent_rev = CapEx / Latest Revenue
  c) D&A from P&L; da_percent_rev = D&A / Latest Revenue

=== STEP 5: MARKET PARAMETERS ===
  a) Beta (from sector if not in document)
  b) Base Fiscal Year (most recent completed FY)

=== STEP 6: CONFIDENCE SELF-ASSESSMENT ===
For each field, rate your confidence from 0.0 to 1.0:
- 1.0 = Found exact number with clear citation
- 0.7 = Calculated from other figures (show calculation)
- 0.4 = Estimated from partial data or industry benchmark
- 0.0 = Could not find, returning null

Now output your work as a single JSON object with this structure:
{{
  "reconciliation_log": "<your step-by-step work from Steps 1-5 as a text string>",
  "historical_revenues": {{"value": [...], "confidence": 0.9, "source": "P&L Statement, Page X"}},
  "historical_ebitda_margins": {{"value": [...], "confidence": 0.85, "source": "Calculated from PBT/Finance/DA"}},
  "net_debt": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet, Note Y"}},
  "total_borrowings": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet"}},
  "lease_liabilities": {{"value": <number_or_null>, "confidence": 0.7, "source": "Balance Sheet / Note on Leases"}},
  "cash_and_equivalents": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet"}},
  "shares_outstanding": {{"value": <exact_absolute_number_or_null>, "confidence": 0.9, "source": "Share Capital Note: [amount] ÷ [face value]"}},
  "diluted_shares_outstanding": {{"value": <exact_absolute_number_or_null>, "confidence": 0.8, "source": "EPS Note (diluted denominator)"}},
  "cap_ex_percent_rev": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Cash Flow Statement"}},
  "da_percent_rev": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "P&L Statement"}},
  "debt_to_equity": {{"value": <decimal_or_null>, "confidence": 0.8, "source": "Balance Sheet"}},
  "beta": {{"value": <decimal_or_null>, "confidence": 0.5, "source": "Sector estimate"}},
  "base_fy": {{"value": <integer_or_null>, "confidence": 0.95, "source": "Cover page"}},
  "currency": "INR"
}}

Return ONLY the JSON. No markdown fences. No extra text before or after.
""".strip()

    # ------------------------------------------------------------------
    # NEW: Auditor (Checker) Prompt
    # ------------------------------------------------------------------

    @staticmethod
    def build_auditor_prompt(extracted_data: dict, audit_trail: list,
                             reconciliation_log: str,
                             company_name: str = "") -> str:
        """
        Prompt for the Auditor agent to verify the Preparer's extraction.
        """
        company_label = company_name or "the target company"

        audit_summary = json.dumps(audit_trail, indent=2, default=str)
        data_summary = json.dumps(extracted_data, indent=2, default=str)

        return f"""
You are auditing the financial data extraction for {company_label}.
A junior analyst (the "Preparer") extracted the following data. Your job is to VERIFY it.

=== PREPARER'S RECONCILIATION WORK ===
{reconciliation_log}

=== EXTRACTED DATA ===
{data_summary}

=== AUDIT TRAIL (per-field confidence & citations) ===
{audit_summary}

=== YOUR AUDIT CHECKLIST ===

1. CITATION VERIFICATION: For each field, check if the stated source makes sense.
   - Revenue should come from "Statement of Profit & Loss" or "Revenue from Operations"
   - Shares should come from "Share Capital" note, NOT face value of shares
   - Net Debt should be calculated from Balance Sheet items

2. MATHEMATICAL VERIFICATION: Check the Preparer's reconciliation math.
   - Does EBITDA = PBT + Finance Costs + D&A?
   - Does Net Debt = Borrowings - Cash?
   - Is EBITDA Margin = EBITDA / Revenue?

3. REASONABLENESS CHECK:
   - Are revenue growth trends consistent year-over-year?
   - Is the EBITDA margin reasonable for the company's industry?
   - Are shares outstanding in a valid Indian range (42 Lakhs to 640 Crores)?

4. ONE-OFF IDENTIFICATION: Check if any adjustments claimed as "one-off" are truly non-recurring.
   - Litigation settlements in highly regulated industries may be recurring
   - Restructuring charges in a company that restructures every 2 years are NOT one-off

Return your verdict as a JSON object:
{{
  "overall_status": "approved" | "flagged" | "rejected",
  "field_verdicts": [
    {{
      "field": "<field_name>",
      "status": "approved" | "flagged" | "rejected",
      "auditor_confidence": <0.0-1.0>,
      "reason": "<explanation>"
    }}
  ],
  "auditor_notes": "<overall summary of findings>",
  "corrections": {{
    "<field_name>": <corrected_value_or_null>
  }}
}}

Only include corrections for fields you believe are WRONG. 
Return ONLY the JSON. No markdown fences.
""".strip()
