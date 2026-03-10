import json


class PromptBuilder:
    @staticmethod
    def get_system_prompt(agent_type: str) -> str:
        prompts = {
            "orchestrator": "You are the AIBAA Orchestrator. Route user requests to the correct specialized analyst agent.",
            "modeling": (
                "You are a senior Investment Banking Analyst specializing in building complex Financial Models "
                "(DCF, LBO, CCA). You are precise, methodical, and trust factual data over assumptions. "
                "You have deep expertise in Indian market valuations across sectors and you understand "
                "Indian GAAP / Ind AS financial statements. All monetary values must be in INR absolute "
                "numbers. You can handle both profitable and loss-making companies."
            ),
            "auditor": (
                "You are a senior Statutory Auditor with 15+ years of experience in Indian GAAP / Ind AS. "
                "Your job is to verify financial data extracted by a junior analyst. You are skeptical, "
                "precise, and follow double-entry accounting principles rigorously. You check citations, "
                "verify calculations, and flag any inconsistencies. You never accept a number without proof."
            ),
            "pitchbook": "You are an IB analyst creating client pitch presentations. You excel at summarizing complex data into high-impact insights.",
            "due_diligence": "You are a legal and financial due diligence reviewer. Your job is to read complex contracts and financial statements and flag potential risks categorized by severity.",
            "research": "You are an equity research analyst. Summarize market landscapes, identify key industry players, and compile buyer universes.",
            "doc_drafter": "You are drafting a Confidential Information Memorandum (CIM). You write with a professional, institutional tone suitable for enterprise buyers.",
            "coordination": "You are a deal coordination specialist. Summarize meetings, extract tasks, and track status.",
        }
        return prompts.get(agent_type, "You are an expert AI Analyst.")

    @staticmethod
    def build_modeling_dcf_prompt(parameters: dict, active_documents_context: str) -> str:
        """Legacy prompt kept for backward compatibility."""
        return f"""
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
You are a financial data extraction engine. Your only job is to extract historical financial data from the provided document context.

EXTRACTION RULES:
1. All monetary values must be in INR absolute numbers, not in lakhs or crores.
2. Revenue = "Revenue from Operations" from the Consolidated Statement of Profit and Loss.
3. EBITDA = PBT + Finance Costs + Depreciation and Amortisation.
4. Net Debt = Total Borrowings - Cash and Equivalents.
5. Shares Outstanding = exact number of equity shares from the Share Capital note.
6. Extract CapEx, D&A, Debt-to-Equity, Beta, and Base Fiscal Year if available.

If you cannot find a specific number, return null for that field. Do not make up numbers.

Return only a raw JSON object:
{{
  "historical_revenues": [year1_inr, year2_inr, year3_inr, year4_inr, year5_inr],
  "historical_ebitda_margins": [year1_margin, year2_margin, year3_margin, year4_margin, year5_margin],
  "net_debt": <number_or_null>,
  "total_borrowings": <number_or_null>,
  "cash_and_equivalents": <number_or_null>,
  "shares_outstanding": <exact_number_or_null>,
  "cap_ex_percent_rev": <decimal_or_null>,
  "da_percent_rev": <decimal_or_null>,
  "debt_to_equity": <decimal_or_null>,
  "beta": <decimal_or_null>,
  "base_fy": <integer_or_null>,
  "currency": "INR"
}}
""".strip()

    @staticmethod
    def build_preparer_prompt(parameters: dict, document_context: str, company_name: str = "") -> str:
        company_label = company_name or "the target company"

        return f"""
You are extracting financial data for {company_label} from annual report documents.

--- Document Context ---
{document_context}
---

You must follow this workflow and reconcile the numbers before you answer.

STEP 0: DETECT REPORTING UNITS
- Look for headers like "(₹ in Crores)", "(₹ in Lakhs)", "(in Millions)", "(in Thousands)" etc.
- This determines the multiplier: Crores = 10,000,000, Lakhs = 100,000, Millions = 1,000,000.
- All monetary values in your JSON output must be converted to absolute INR (i.e. multiply by the unit).
- For example, if the document says revenue is 117,055 in Crores, return 1170550000000 (117055 × 10000000).
- If the document says revenue is 1,17,055 in Lakhs, return 11705500000 (117055 × 100000).
- Report the detected unit in the "reporting_unit" field.

STEP 1: IDENTIFY BASE FIGURES
- Identify the company legal form and listing status first.
- Determine whether this is a large-cap, mid-cap, or small-cap company from the revenue scale.
- Extract the CIN if shown.
- Explicitly detect pre-IPO indicators such as DRHP/P-DRHP filing, proposed listing, and unlisted status.
- Find "Revenue from Operations" from the Consolidated Statement of Profit and Loss.
- Extract up to 5 years of historical revenue.
- State the page or section where you found each number.
- All monetary values must be returned in INR absolute numbers (after unit conversion).
- SANITY CHECK: For a large-cap Indian listed company, revenue should be ₹10,000 Crores+ (₹100B+). For mega-cap IT companies like TCS, Infosys, HCL, revenue is ₹50,000+ Crores.

STEP 2: EBITDA RECONCILIATION
- For each year, compute EBITDA as:
  a) Profit Before Tax
  b) plus Finance Costs
  c) plus Depreciation and Amortisation
  d) equals EBITDA
  e) EBITDA Margin = EBITDA / Revenue
- Negative margins are valid for loss-making companies.
- For IT services companies, EBITDA margins typically range from 18-28%.

STEP 3: BALANCE SHEET EXTRACTION
- Total Borrowings = Current Borrowings + Non-Current Borrowings (including term loans, debentures, commercial paper).
- CCPS Liability (or preference share liability measured as financial liability) must be extracted separately when disclosed.
- Lease Liabilities = Current Lease Liabilities + Non-Current Lease Liabilities.
- Cash and Equivalents = Cash + Bank Balances + Current Investments + Other Liquid Investments.
- Include term deposits/bank balances with maturity > 12 months if they are unrestricted cash-like balances.
- IT services and technology companies typically hold enormous cash positions (30-60% of revenue in cash + investments).
  Look carefully in BOTH current and non-current sections for:
  * Cash and cash equivalents
  * Other bank balances / term deposits
  * Current investments / treasury investments / mutual fund units
  * Non-current investments (liquid mutual funds, bonds, government securities)
  * Earmarked/restricted balances (include only if unrestricted)
  Sum ALL of these to get the complete cash position. Missing even one category will significantly understate the value.
- Net Debt = Total Borrowings + Lease Liabilities + CCPS Liability - Cash and Equivalents.
- If the company is net-cash positive (cash > debt), Net Debt will be negative. This is valid and common for IT companies.
- Shares Outstanding:
  - Find "Issued, Subscribed and Fully Paid-Up" in the Share Capital note.
  - Extract the exact number of equity shares if shown.
  - If only amount and face value are shown, compute shares = share capital amount / face value per share.
  - CRITICAL CROSS-CHECK: Verify shares using EPS calculation:
    shares = Profit After Tax / Basic EPS
    This should match the Share Capital note. If it doesn't, explain the discrepancy.
  - Also extract diluted shares if available.
  - Return shares as an absolute number, not in crores or lakhs.
  - Large-cap Indian companies typically have 50 Crore to 700 Crore shares (500M to 7B).
  - Never infer shares from market cap, stock price, or external knowledge.
- Debt-to-Equity = (Total Borrowings + Lease Liabilities) / Shareholders' Equity.

STEP 4: CASH FLOW STATEMENT
- CapEx = Purchase of Property, Plant and Equipment or Additions to Fixed Assets.
- For asset-light IT services companies, CapEx is typically 3-5% of revenue.
- cap_ex_percent_rev = CapEx / Latest Revenue.
- D&A from P&L and da_percent_rev = D&A / Latest Revenue.
- Operating Cash Flow (OCF) = "Cash generated from operations" or "Net cash from operating activities".
  Extract this as an absolute INR number. OCF is a critical cross-check:
  * For profitable IT companies, OCF is typically 80-120% of PAT.
  * FCF ≈ OCF - CapEx. If FCF seems unreasonably low, check whether OCF was missed.

STEP 5: MARKET PARAMETERS
- Beta from the document if available. If not available in the document, return null.
- For listed companies, if beta is not in the document, note the sector for estimation.
- Base Fiscal Year = the most recent completed fiscal year.
- If annual report contains fair-value valuation assumptions, extract:
  - discount_rate_reference
  - forecast_revenue_growth_range
  - terminal_growth_reference
- Identify the company's primary industry/sector for appropriate WACC estimation.

STEP 6: CONFIDENCE SELF-ASSESSMENT
- 1.0 = exact number with citation
- 0.7 = calculated from cited figures
- 0.4 = estimated from partial data
- 0.0 = not found

Return only one JSON object with this structure:
{{
  "reconciliation_log": "<step-by-step notes as a text string>",
  "company_legal_form": {{"value": "<string_or_null>", "confidence": 0.95, "source": "Cover page / corporate information"}},
  "listing_status": {{"value": "<private|public|listed|unlisted|unknown>", "confidence": 0.8, "source": "Company name / CIN / annual report"}},
  "cin": {{"value": "<string_or_null>", "confidence": 0.95, "source": "Corporate information / annual report cover"}},
  "historical_revenues": {{"value": [...], "confidence": 0.9, "source": "P&L Statement, Page X"}},
  "historical_ebitda_margins": {{"value": [...], "confidence": 0.85, "source": "Calculated from PBT, finance cost, and D&A"}},
  "net_debt": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet / Notes"}},
  "total_borrowings": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet / Notes"}},
  "ccps_liability": {{"value": <number_or_null>, "confidence": 0.8, "source": "Financial liabilities note / fair value note"}},
  "lease_liabilities": {{"value": <number_or_null>, "confidence": 0.7, "source": "Lease note / Balance Sheet"}},
  "cash_and_equivalents": {{"value": <number_or_null>, "confidence": 0.8, "source": "Balance Sheet / Notes"}},
  "shares_outstanding": {{"value": <number_or_null>, "confidence": 0.9, "source": "Share Capital note or computed from paid-up capital / face value"}},
  "diluted_shares_outstanding": {{"value": <number_or_null>, "confidence": 0.8, "source": "EPS note"}},
  "cap_ex_percent_rev": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Cash Flow Statement"}},
  "da_percent_rev": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "P&L Statement"}},
  "debt_to_equity": {{"value": <decimal_or_null>, "confidence": 0.8, "source": "Balance Sheet"}},
  "beta": {{"value": <decimal_or_null>, "confidence": 0.5, "source": "Document or sector estimate"}},
  "discount_rate_reference": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Fair value measurement / valuation note"}},
  "forecast_revenue_growth_low": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Fair value sensitivity / valuation note"}},
  "forecast_revenue_growth_high": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Fair value sensitivity / valuation note"}},
  "terminal_growth_reference": {{"value": <decimal_or_null>, "confidence": 0.7, "source": "Fair value sensitivity / valuation note"}},
  "base_fy": {{"value": <integer_or_null>, "confidence": 0.95, "source": "Annual report cover or statements header"}},
  "reporting_unit": {{"value": "<crores|lakhs|millions|absolute>", "confidence": 0.95, "source": "Statement header / notes to accounts"}},
  "industry_sector": {{"value": "<string>", "confidence": 0.8, "source": "Company description / segment reporting"}},
  "profit_after_tax": {{"value": <number_or_null>, "confidence": 0.9, "source": "P&L Statement"}},
  "basic_eps": {{"value": <number_or_null>, "confidence": 0.9, "source": "P&L Statement / EPS note"}},
  "operating_cash_flow": {{"value": <number_or_null>, "confidence": 0.8, "source": "Cash Flow Statement"}},
  "currency": "INR"
}}
""".strip()

    @staticmethod
    def build_auditor_prompt(extracted_data: dict, audit_trail: list, reconciliation_log: str, company_name: str = "") -> str:
        company_label = company_name or "the target company"
        audit_summary = json.dumps(audit_trail, indent=2, default=str)
        data_summary = json.dumps(extracted_data, indent=2, default=str)

        return f"""
You are auditing the financial data extraction for {company_label}.
A junior analyst extracted the following data. Your job is to verify it.

=== PREPARER RECONCILIATION WORK ===
{reconciliation_log}

=== EXTRACTED DATA ===
{data_summary}

=== AUDIT TRAIL ===
{audit_summary}

Audit checklist:
1. Citation verification
- Company type should be supported by legal name, CIN, or annual-report disclosures.
- Revenue should come from the Statement of Profit and Loss.
- Shares should come from the Share Capital note or an explicit paid-up-capital divided by face-value calculation.
- Net debt should come from balance sheet items.

2. Mathematical verification
- EBITDA = PBT + Finance Costs + D&A.
- Net Debt = Borrowings + Lease Liabilities - Cash.
- EBITDA Margin = EBITDA / Revenue.

3. Reasonableness checks
- Are the growth trends internally consistent?
- Are shares outstanding within a plausible Indian listed-company range?
- Do the assumptions look like extracted facts or unsupported estimates?

Return only a JSON object:
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
  "auditor_notes": "<overall summary>",
  "corrections": {{
    "<field_name>": <corrected_value_or_null>
  }}
}}
""".strip()
