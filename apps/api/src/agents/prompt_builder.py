class PromptBuilder:
    @staticmethod
    def get_system_prompt(agent_type: str) -> str:
        prompts = {
            "orchestrator": "You are the AIBAA Orchestrator. Route user requests to the correct specialized analyst agent.",
            "modeling": "You are a senior Investment Banking Analyst specializing in building complex Financial Models (DCF, LBO, CCA). You are precise, methodical, and trust factual data over assumptions. You have deep expertise in Indian market valuations across all sectors — manufacturing, fintech, SaaS, healthcare, FMCG, and consumer tech. You understand Indian GAAP/Ind AS financial statements. All monetary values must be in INR absolute numbers. You can handle both profitable and LOSS-MAKING companies.",
            "pitchbook": "You are an IB analyst creating client pitch presentations. You excel at summarizing complex data into high-impact insights.",
            "due_diligence": "You are a legal and financial due diligence reviewer. Your job is to read complex contracts and financial statements and flag potential risks categorized by severity.",
            "research": "You are an equity research analyst. Summarize market landscapes, identify key industry players, and compile buyer universes.",
            "doc_drafter": "You are drafting a Confidential Information Memorandum (CIM). You write with a professional, institutional tone suitable for enterprise buyers.",
            "coordination": "You are a deal coordination specialist. Summarize meetings, extract tasks, and track status."
        }
        return prompts.get(agent_type, "You are an expert AI Analyst.")

    @staticmethod
    def build_modeling_dcf_prompt(parameters: dict, active_documents_context: str) -> str:
        """Specific prompt format for the DCF modeling task."""
        
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
   Look for FY2021 through FY2025, or whatever years are available.
   PAY ATTENTION TO ACTUAL GROWTH TRENDS — if revenue is declining, report the declining numbers accurately.

3. EBITDA = PBT + Finance Costs + Depreciation & Amortisation. EBITDA Margin = EBITDA / Revenue.
   IMPORTANT: EBITDA margins CAN BE NEGATIVE for loss-making companies (e.g. Paytm, Zomato, Ola).
   Return negative margins as negative decimals (e.g. -0.22 for -22% margin).
   Do NOT confuse Contribution Margin with EBITDA Margin — they are different.

4. Net Debt = Total Borrowings (current + non-current) - Cash & Bank Balances - Current Investments.
   If Cash > Borrowings, the company is NET CASH. Return net_debt as NEGATIVE.
   If the company has ZERO BORROWINGS, return net_debt as 0 and debt_to_equity as 0.
   
5. Extract total_borrowings and cash_and_equivalents SEPARATELY from the Balance Sheet.

6. Shares Outstanding = Total number of equity shares from Share Capital note.
   CRITICAL: Look for "Number of shares" in the Share Capital note, NOT the face value amount.
   Example: If Share Capital = ₹49.78 Cr at face value ₹1/share, then shares = 49,78,00,000 (49.78 Cr shares).
   Example: If Share Capital = ₹24.89 Cr at face value ₹1/share, then shares = 24,89,00,000 (24.89 Cr shares).
   Example: If Share Capital = ₹10 Cr at face value ₹2/share, then shares = 5,00,00,000 (5 Cr shares).
   Search for: "Subscribed and fully paid-up", "Number of equity shares", authorised/issued/paid-up capital.
   Indian companies can have shares ranging from ~42 Lakhs (4.2M) to ~640 Crores (6.4B).
   Always extract the EXACT number. Do NOT round or assume.

7. CapEx: Extract "Purchase of Property, Plant and Equipment" (or "Additions to Fixed Assets")
   from the Cash Flow Statement. Calculate cap_ex_percent_rev = CapEx / Revenue.
   Typical range: 1% to 15% depending on industry. Manufacturing: 3-8%. IT/Services: 1-3%.

8. Depreciation & Amortisation: Extract D&A from the Statement of Profit & Loss.
   Calculate da_percent_rev = D&A / Revenue. Typical range: 2% to 8%.

9. Debt-to-Equity Ratio: Calculate from Balance Sheet as Total Debt / Total Shareholders' Equity.
   If company has ZERO debt, return 0.0. Do NOT assume a default D/E ratio.

10. Beta: If available in documents or identifiable from sector, provide it.
    Consumer Staples (FMCG, Footwear): 0.7-1.0. IT Services: 0.8-1.1. Banks/NBFC: 1.0-1.3.
    If not available, return null and system will use sector-appropriate default.

11. Base Fiscal Year: Identify the MOST RECENT completed fiscal year in the documents.
    Indian companies typically end fiscal year on March 31.
    Example: "Year ended March 31, 2025" → base_fy = 2025.

If you cannot find a specific number, return null for that field. Do NOT make up numbers and do NOT use an example number. You must dig through the text to find the actual figures.

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
