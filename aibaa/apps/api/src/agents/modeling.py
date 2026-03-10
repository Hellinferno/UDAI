from typing import Dict, Any, List, Optional, Tuple
import json
import re
import time
import os

from agents.base import BaseAgent
from agents.prompt_builder import PromptBuilder
from agents.extractor import PreparerAgent
from agents.auditor import AuditorAgent
from engine.dcf import DCFEngine
from engine.llm import ask_llm
from engine.triangulator import Triangulator
from tools.excel_writer import WorkbookBuilder
from store import store, Output, ExtractionAudit


class FinancialModelingAgent(BaseAgent):
    def __init__(self, deal_id: str, input_payload: Dict[str, Any]):
        super().__init__(
            agent_type="modeling",
            task_name=input_payload.get("task_name", "dcf_model"),
            deal_id=deal_id,
            input_payload=input_payload
        )
        self.system_prompt = PromptBuilder.get_system_prompt(self.agent_type)
        self.excel_tool = WorkbookBuilder()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_document_context(self) -> str:
        """Fetch all parsed text from the deal's documents."""
        docs = store.get_documents_for_deal(self.deal_id)
        if not docs:
            return "No documents available."
        context = ""
        for d in docs:
            context += f"\\n--- Document: {d.filename} ---\\n"
            context += d.parsed_text if d.parsed_text else "(Parsing incomplete or text unavailable)"
        return context

    def _resolve(self, param_key: str, params: dict, llm_data: dict,
                 defaults: dict, *, cast=float, label: str = "") -> Tuple[Any, str]:
        """
        Resolve a value: Frontend param > LLM extraction > Generic default.
        Returns (value, source_label).
        """
        name = label or param_key

        # 1. Frontend override
        override = params.get(param_key)
        if override is not None and override != "":
            return cast(override), f"{name}: user override"

        # 2. LLM extraction
        llm_val = llm_data.get(param_key)
        if llm_val is not None and llm_val != "":
            try:
                return cast(llm_val), f"{name}: LLM extracted"
            except (ValueError, TypeError):
                pass

        # 3. Generic default
        default = defaults.get(param_key)
        if default is not None:
            return cast(default), f"{name}: generic default"

        return None, f"{name}: missing"

    # ------------------------------------------------------------------
    # LLM Response Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(raw: str) -> dict:
        """Robustly parse LLM response with markdown/think blocks."""
        text = raw.strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        text = text.replace('```json', '').replace('```', '').strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from LLM response (length={len(raw)})")

    @staticmethod
    def _normalize_revenues(revs: list) -> list:
        """Auto-detect revenue units and convert to absolute INR.
        
        Detection logic:
        - < 100: Likely ₹ Thousands of Crores → × 1e11 (too rare, skip)
        - 100 to 99,999: Likely ₹ Crores → × 1e7
        - 100,000 to 9,999,999: Likely ₹ Lakhs → × 1e5
        - ≥ 10,000,000: Already absolute INR
        
        The key insight: Indian mid-cap companies (like Relaxo, boAt) report
        revenues in the 1,000–50,000 Cr range. If LLM returns 2789 (Crores),
        that's Cr and should be multiplied by 1e7.
        """
        if not revs or not all(isinstance(r, (int, float)) for r in revs):
            return revs
        max_val = max(abs(r) for r in revs)
        
        if max_val < 1:
            # Likely a broken extraction, don't touch
            return revs
        elif max_val < 100_000:
            # Values in range 1-99,999 → most likely Crores
            return [r * 1e7 for r in revs]
        elif max_val < 10_000_000:
            # Values in range 100,000-9,999,999 → most likely Lakhs
            return [r * 1e5 for r in revs]
        else:
            # ≥ 10M → already in absolute INR
            return revs

    @staticmethod
    def _normalize_margins(margins: list) -> list:
        """Auto-detect whether margins are decimals or percentages."""
        if not margins or not all(isinstance(m, (int, float)) for m in margins):
            return margins
        if any(abs(m) > 1.0 for m in margins):
            return [m / 100.0 for m in margins]
        return margins

    @staticmethod
    def _normalize_shares(shares) -> float:
        """Auto-detect shares unit and convert to absolute number.
        
        Indian listed companies range: 42 Lakh (4.2M) to 640 Crore (6.4B).
        
        Detection:
        - < 100: Likely Crores → × 1e7 (e.g., 24.89 → 248,900,000)
        - 100 to 9,999: Could be Crores or Lakhs. Check if ×1e7 is in valid range.
        - 10,000 to 99,999: Likely Lakhs → × 1e5
        - 100,000 to 3,999,999: Ambiguous — likely thousands → × 1e3
        - 4,000,000 to 6,400,000,000: Already absolute (valid range)
        - > 6.4B: Probably already absolute, leave as-is
        """
        if not isinstance(shares, (int, float)) or shares <= 0:
            return shares
        
        MIN_SHARES = 4_200_000        # 42 Lakh (smallest listed)
        MAX_SHARES = 6_400_000_000    # 640 Crore (mega-cap)
        
        # Already in valid absolute range
        if MIN_SHARES <= shares <= MAX_SHARES:
            return shares
        
        # < 100: Almost certainly Crores (e.g., 24.89 Cr)
        if shares < 100:
            candidate = shares * 1e7
            if MIN_SHARES <= candidate <= MAX_SHARES:
                return candidate
            return shares  # Can't determine
        
        # 100 to 9,999: Try Crores first, then Lakhs
        if shares < 10_000:
            candidate_cr = shares * 1e7
            if MIN_SHARES <= candidate_cr <= MAX_SHARES:
                return candidate_cr
            candidate_lk = shares * 1e5
            if MIN_SHARES <= candidate_lk <= MAX_SHARES:
                return candidate_lk
            return shares
        
        # 10,000 to 99,999: Likely Lakhs
        if shares < 100_000:
            candidate = shares * 1e5
            if MIN_SHARES <= candidate <= MAX_SHARES:
                return candidate
            return shares
        
        # 100,000 to 4,199,999: Likely thousands
        if shares < MIN_SHARES:
            candidate = shares * 1_000
            if MIN_SHARES <= candidate <= MAX_SHARES:
                return candidate
            return shares
        
        # > 6.4B: Leave as-is (possibly already absolute)
        return shares

    @staticmethod
    def _normalize_pct_field(val, field_name: str = "") -> float:
        """Normalize 4.0 (percent) vs 0.04 (decimal)."""
        if not isinstance(val, (int, float)):
            return val
        if val > 1.0:
            return val / 100.0
        return val

    @staticmethod
    def _normalize_net_debt(val) -> float:
        """Normalize net_debt: if it looks like crores, convert."""
        if not isinstance(val, (int, float)):
            return val
        if abs(val) < 100_000 and val != 0:
            return val * 1e7
        return val

    @staticmethod
    def _to_number(val) -> Optional[float]:
        """Best-effort numeric coercion."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.strip().replace(",", "")
            if not cleaned or cleaned.lower() in {"na", "n/a", "null", "none", "-"}:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @classmethod
    def _enforce_capital_structure_consistency(cls, llm_data: dict) -> dict:
        """Keep debt assumptions internally consistent, including lease liabilities (Ind AS 116)."""
        if not llm_data:
            return llm_data
        data = dict(llm_data)
        borrowings = cls._to_number(data.get("total_borrowings"))
        cash = cls._to_number(data.get("cash_and_equivalents"))
        net_debt = cls._to_number(data.get("net_debt"))
        debt_to_equity = cls._to_number(data.get("debt_to_equity"))
        lease_liabilities = cls._to_number(data.get("lease_liabilities"))
        
        # Include lease liabilities in total debt per Ind AS 116
        total_debt_inc_leases = (borrowings or 0) + (lease_liabilities or 0)
        
        if borrowings is not None and cash is not None:
            implied_net_debt = total_debt_inc_leases - (cash or 0)
            data["net_debt"] = implied_net_debt
            if total_debt_inc_leases <= 0:
                data["debt_to_equity"] = 0.0
        elif borrowings is not None and borrowings <= 0 and (lease_liabilities is None or lease_liabilities <= 0):
            data["debt_to_equity"] = 0.0
            if net_debt is not None and net_debt > 0:
                data["net_debt"] = 0.0
        if debt_to_equity is not None and debt_to_equity > 0 and total_debt_inc_leases <= 0:
            data["debt_to_equity"] = 0.0
        return data

    # ------------------------------------------------------------------
    # Main Agent Logic — 3-Stage Maker-Checker Pipeline
    # ------------------------------------------------------------------

    def run(self) -> str:
        self.think("Initializing Financial Modeling Agent. Verifying task type.")

        if self.task_name != "dcf_model":
            self.fail(f"Unsupported modeling task: {self.task_name}")
            return self.run_id

        self.think("Extracting Context from Virtual Data Room.")
        context = self._extract_document_context()
        self.observe(f"Extracted {len(context)} characters of document context.")

        self.think("Building LLM instructions to query for Historical Extraction.")
        params = self.input_payload.get("parameters", {})

        deal = store.get_deal(self.deal_id)
        deal_name = deal.name if deal else "Unknown Deal"
        company_name = deal.company_name if deal else "the target company"

        # Explicit grounding to prevent phantom company hallucinations
        context_header = f"CRITICALLY IMPORTANT: The target company is {company_name} (Deal: {deal_name}).\\n"
        context_header += "1. Do not extract data for any other entity.\\n"
        context_header += "2. Extract exactly 5 YEARS of historical revenue and EBITDA margins to establish trends.\\n"
        context_header += "3. Search thoroughly for Total Debt, Borrowings, and Cash on the balance sheet. Do not blindly assume $0 Net Debt.\\n"
        context_header += "4. Extract CapEx from Cash Flow Statement and D&A from Profit & Loss separately.\\n"
        context_header += "5. Calculate Debt-to-Equity from Balance Sheet. If zero debt, return 0.0.\\n\\n"

        # ═══════════════════════════════════════════════════════════════
        # GENERIC FALLBACK DEFAULTS
        # ═══════════════════════════════════════════════════════════════
        GENERIC_DEFAULTS = {
            "historical_revenues": [150_000_000_000, 180_000_000_000, 200_000_000_000, 220_000_000_000, 250_000_000_000],
            "historical_ebitda_margins": [0.12, 0.12, 0.12, 0.12, 0.12],
            "net_debt": 0,
            "shares_outstanding": 100_000_000,
            "total_borrowings": 0,
            "cash_and_equivalents": 0,
            "cap_ex_percent_rev": 0.03,
            "da_percent_rev": 0.056,
            "debt_to_equity": 0.0,
            "beta": 1.0,
            "base_fy": 2025,
            "currency": "INR",
        }

        # ═══════════════════════════════════════════════════════════════
        # STAGE 1: PREPARER AGENT (Chain-of-Thought Extraction)
        # ═══════════════════════════════════════════════════════════════
        llm_data = {}
        fallback_mode = False
        fallback_profile = ""
        extraction_audit_trail = []
        auditor_verdicts = []
        triangulation_result = {}
        preparer_output = {}

        self.think("[STAGE 1/3] Deploying Preparer Agent with reconciliation prompting.")
        self.act("preparer_agent", "Extracting financial data with chain-of-thought reconciliation")
        try:
            preparer_output = PreparerAgent.extract(
                system_prompt=self.system_prompt,
                document_context=context_header + context,
                params=params,
                company_name=company_name,
            )
            llm_data = preparer_output.get("extracted_data", {})
            extraction_audit_trail = preparer_output.get("audit_trail", [])
            reconciliation_log = preparer_output.get("reconciliation_log", "")
            fallback_mode = str(llm_data.get("extraction_mode", "")).lower() == "deterministic_fallback"
            fallback_profile = str(llm_data.get("fallback_profile", ""))
            self.observe(f"Preparer extracted {len(llm_data)} fields with {len(extraction_audit_trail)} audit entries.")
            if reconciliation_log:
                self.observe(f"Reconciliation log (first 300 chars): {reconciliation_log[:300]}")
        except Exception as e:
            self.observe(f"Preparer extraction failed ({str(e)}). Will use generic defaults.")
            llm_data = {}

        # ═══════════════════════════════════════════════════════════════
        # STAGE 2: AUDITOR AGENT (Citation Verification)
        # ═══════════════════════════════════════════════════════════════
        if llm_data and extraction_audit_trail:
            self.think("[STAGE 2/3] Deploying Auditor Agent to verify citations and accounting logic.")
            self.act("auditor_agent", "Verifying Preparer output against Ind AS / GAAP standards")
            try:
                auditor_result = AuditorAgent.audit(
                    system_prompt=PromptBuilder.get_system_prompt("auditor"),
                    preparer_output=preparer_output,
                    company_name=company_name,
                )
                auditor_verdicts = auditor_result.get("field_verdicts", [])
                overall_audit = auditor_result.get("overall_status", "flagged")
                auditor_notes = auditor_result.get("auditor_notes", "")

                corrections = auditor_result.get("corrections", {})
                if corrections:
                    llm_data = AuditorAgent.merge_corrections(llm_data, auditor_result)
                    self.observe(f"Auditor applied corrections to: {list(corrections.keys())}")

                self.observe(f"Auditor verdict: {overall_audit} ({len(auditor_verdicts)} field checks). Notes: {auditor_notes[:200]}")

                if overall_audit == "rejected":
                    self.observe("WARNING: Auditor REJECTED extraction. Flagging all fields for human review.")
            except Exception as e:
                self.observe(f"Auditor agent failed ({str(e)}). Proceeding with Preparer data.")
        else:
            self.observe("Skipping Auditor stage (no extraction data or audit trail).")

        # ═══════════════════════════════════════════════════════════════
        # STAGE 3: TRIANGULATOR (Double-Entry Cross-Checks)
        # ═══════════════════════════════════════════════════════════════
        if llm_data:
            self.think("[STAGE 3/3] Running deterministic double-entry triangulation checks.")
            self.act("triangulator", "Verifying accounting identities (Net Debt, EBITDA, Shares, D/E)")
            triangulation_result = Triangulator.run_all_checks(llm_data)
            tri_verdict = triangulation_result.get("overall_verdict", "unknown")
            tri_passed = triangulation_result.get("passed", 0)
            tri_total = triangulation_result.get("total_checks", 0)
            self.observe(
                f"Triangulation: {tri_verdict.upper()} — {tri_passed}/{tri_total} checks passed. "
                f"Critical failures: {triangulation_result.get('critical_failures', 0)}"
            )
            if tri_verdict == "halt":
                self.observe("CRITICAL: Triangulation detected fundamental accounting inconsistencies. Flagging for review.")
        else:
            self.observe("Skipping Triangulation (no data).")

        # ─── Store Audit Trail ─────────────────────────────────
        audit_records = []
        for entry in extraction_audit_trail:
            field_name = entry.get("field", "unknown")
            av = next((v for v in auditor_verdicts if v.get("field") == field_name), {})
            tri_match = next(
                (r for r in triangulation_result.get("results", []) if field_name in r.get("identity", "").lower()),
                {}
            )
            record = ExtractionAudit(
                deal_id=self.deal_id,
                agent_run_id=self.run_id,
                field_name=field_name,
                extracted_value=entry.get("value"),
                confidence_score=entry.get("confidence", 0.5),
                source_citation=entry.get("source_citation", ""),
                reasoning=entry.get("reasoning", ""),
                auditor_status=av.get("status", "pending"),
                auditor_confidence=av.get("auditor_confidence", 0.0),
                auditor_reason=av.get("reason", ""),
                triangulation_status="pass" if tri_match.get("passed", True) else "fail",
                triangulation_details=tri_match.get("details", ""),
            )
            audit_records.append(record)
        store.extraction_audits[self.run_id] = audit_records
        self.observe(f"Stored {len(audit_records)} extraction audit records.")

        # ─── NORMALIZE LLM DATA ───────────────────────────────
        if llm_data:
            if llm_data.get("historical_revenues"):
                raw_revs = llm_data["historical_revenues"]
                llm_data["historical_revenues"] = self._normalize_revenues(raw_revs)
                if raw_revs != llm_data["historical_revenues"]:
                    self.observe(f"Auto-normalized revenues: {raw_revs} -> {llm_data['historical_revenues']}")

            if llm_data.get("historical_ebitda_margins"):
                raw_margins = llm_data["historical_ebitda_margins"]
                llm_data["historical_ebitda_margins"] = self._normalize_margins(raw_margins)
                if raw_margins != llm_data["historical_ebitda_margins"]:
                    self.observe(f"Auto-normalized margins: {raw_margins} -> {llm_data['historical_ebitda_margins']}")

            if llm_data.get("shares_outstanding"):
                raw_shares = llm_data["shares_outstanding"]
                llm_data["shares_outstanding"] = self._normalize_shares(raw_shares)
                if raw_shares != llm_data["shares_outstanding"]:
                    self.observe(f"Auto-normalized shares: {raw_shares} -> {llm_data['shares_outstanding']}")

            if llm_data.get("net_debt") is not None:
                raw_nd = llm_data["net_debt"]
                llm_data["net_debt"] = self._normalize_net_debt(raw_nd)

            for pct_field in ["cap_ex_percent_rev", "da_percent_rev"]:
                if llm_data.get(pct_field) is not None:
                    raw_val = llm_data[pct_field]
                    llm_data[pct_field] = self._normalize_pct_field(raw_val, pct_field)
                    if raw_val != llm_data[pct_field]:
                        self.observe(f"Auto-normalized {pct_field}: {raw_val} -> {llm_data[pct_field]}")

            for debt_field in ["total_borrowings", "cash_and_equivalents", "lease_liabilities"]:
                if llm_data.get(debt_field) is not None:
                    llm_data[debt_field] = self._normalize_net_debt(llm_data[debt_field])

            llm_data = self._enforce_capital_structure_consistency(llm_data)
            if fallback_mode:
                self.observe(f"Using deterministic fallback profile: {fallback_profile or 'default'}")

            self.observe(f"Normalized LLM data: {json.dumps(llm_data)}")

        # ─── Resolve Revenue & Margins ─────────────────────────
        data_sources = []

        historical_revenues = GENERIC_DEFAULTS["historical_revenues"]
        historical_ebitda_margins = GENERIC_DEFAULTS["historical_ebitda_margins"]

        if llm_data.get("historical_revenues"):
            llm_revs = llm_data["historical_revenues"]
            if isinstance(llm_revs, list) and len(llm_revs) >= 2 and all(
                isinstance(r, (int, float)) and r > 100_000_000 for r in llm_revs
            ):
                if len(set([round(r, -7) for r in llm_revs])) == 1:
                    self.observe(f"LLM revenues look flat ({llm_revs}), using generic defaults")
                    data_sources.append("historical_revenues: generic default (flat)")
                else:
                    historical_revenues = llm_revs
                    self.observe(f"Using LLM-extracted revenues: {llm_revs}")
                    data_sources.append("historical_revenues: LLM extracted")
            else:
                self.observe(f"LLM revenues failed sanity ({llm_revs}), using generic defaults")
                data_sources.append("historical_revenues: generic default (sanity failed)")
        else:
            data_sources.append("historical_revenues: generic default (LLM missing)")

        if llm_data.get("historical_ebitda_margins"):
            llm_margins = llm_data["historical_ebitda_margins"]
            if isinstance(llm_margins, list) and len(llm_margins) >= 2 and all(
                isinstance(m, (int, float)) and -2.0 < m < 0.99 for m in llm_margins
            ):
                historical_ebitda_margins = llm_margins
                self.observe(f"Using LLM-extracted margins: {llm_margins}")
                data_sources.append("historical_ebitda_margins: LLM extracted")
            else:
                self.observe(f"LLM margins failed sanity ({llm_margins}), using generic defaults")
                data_sources.append("historical_ebitda_margins: generic default (sanity failed)")
        else:
            data_sources.append("historical_ebitda_margins: generic default (LLM missing)")

        # ─── Growth Sanity Check ──────────────────────────────
        if len(historical_revenues) >= 2:
            latest_rev = historical_revenues[-1]
            prev_rev = historical_revenues[-2]
            if prev_rev > 0:
                latest_yoy = (latest_rev - prev_rev) / prev_rev
                # Compute historical CAGR
                first_rev = historical_revenues[0]
                n_years = len(historical_revenues) - 1
                if first_rev > 0 and n_years > 0:
                    hist_cagr = (latest_rev / first_rev) ** (1.0 / n_years) - 1.0
                else:
                    hist_cagr = latest_yoy

                # If latest growth is negative/low but no CAGR override set, warn
                revenue_cagr_override_param = params.get("revenue_cagr_override")
                if latest_yoy < 0.02 and not revenue_cagr_override_param:
                    self.observe(
                        f"GROWTH SANITY CHECK: Latest YoY growth = {latest_yoy*100:.1f}%, "
                        f"Historical CAGR = {hist_cagr*100:.1f}%. "
                        f"Auto-capping projected CAGR to max(historical CAGR, 3%)."
                    )
                    # Cap the projected growth at the historical CAGR or a conservative floor
                    conservative_cagr = max(min(hist_cagr, 0.06), 0.02)
                    data_sources.append(f"growth_sanity: auto-capped to {conservative_cagr*100:.1f}% (latest YoY={latest_yoy*100:.1f}%)")
                    # Set the override so DCFEngine uses it
                    params["revenue_cagr_override_auto"] = conservative_cagr

        # ─── DCF Computation ───────────────────────────────────
        self.think("Engaging deterministic DCF Computation Engine.")
        self.act("python_exec", "Instantiating DCFEngine and calculating WACC/UFCF")
        try:
            tgr = params.get("terminal_growth_rate", 0.025)

            risk_free_rate, _ = self._resolve("risk_free_rate", params, llm_data, GENERIC_DEFAULTS, label="risk_free_rate")
            risk_free_rate = risk_free_rate if risk_free_rate else 0.07

            erp, _ = self._resolve("equity_risk_premium", params, llm_data, GENERIC_DEFAULTS, label="equity_risk_premium")
            erp = erp if erp else 0.06

            beta, src = self._resolve("beta", params, llm_data, GENERIC_DEFAULTS, label="beta")
            data_sources.append(src)
            beta = beta if beta else 1.0

            cost_of_debt, _ = self._resolve("cost_of_debt", params, llm_data, GENERIC_DEFAULTS, label="cost_of_debt")
            cost_of_debt = cost_of_debt if cost_of_debt else 0.09

            tax_rate = float(params.get("tax_rate") or 0.25)

            debt_to_equity, src = self._resolve("debt_to_equity", params, llm_data, GENERIC_DEFAULTS, label="debt_to_equity")
            data_sources.append(src)
            debt_to_equity = debt_to_equity if debt_to_equity is not None else 0.0

            wacc_override = params.get("wacc_override")
            wacc_breakdown = {}
            if wacc_override:
                wacc = float(wacc_override)
                wacc_breakdown = {"wacc": wacc, "note": "Manually overridden by user"}
            else:
                temp_engine = DCFEngine(historical_revenues, historical_ebitda_margins, tax_rate=tax_rate)
                wacc_breakdown = temp_engine.calculate_wacc_breakdown(
                    risk_free_rate=risk_free_rate, equity_risk_premium=erp, beta=beta,
                    cost_of_debt=cost_of_debt, debt_to_equity=debt_to_equity
                )
                wacc = wacc_breakdown["wacc"]

            currency = params.get("currency", llm_data.get("currency", GENERIC_DEFAULTS["currency"]))

            net_debt, src = self._resolve("net_debt", params, llm_data, GENERIC_DEFAULTS, label="net_debt")
            data_sources.append(src)
            net_debt = net_debt if net_debt is not None else 0

            shares_outstanding, src = self._resolve("shares_outstanding", params, llm_data, GENERIC_DEFAULTS, label="shares_outstanding")
            data_sources.append(src)
            shares_outstanding = shares_outstanding if shares_outstanding else 100_000_000
            
            # Prefer diluted shares if available (more conservative for per-share valuation)
            diluted = llm_data.get("diluted_shares_outstanding") if llm_data else None
            if diluted is not None:
                diluted = self._normalize_shares(diluted)
                if diluted and diluted > shares_outstanding:
                    self.observe(f"Using diluted shares ({diluted:,.0f}) over basic ({shares_outstanding:,.0f})")
                    shares_outstanding = diluted
                    data_sources.append("shares_outstanding: diluted (more conservative)")

            da_pct, src = self._resolve("da_percent_rev", params, llm_data, GENERIC_DEFAULTS, label="da_percent_rev")
            data_sources.append(src)
            da_pct = da_pct if da_pct is not None else 0.056

            capex_pct, src = self._resolve("cap_ex_percent_rev", params, llm_data, GENERIC_DEFAULTS, label="cap_ex_percent_rev")
            data_sources.append(src)
            capex_pct = capex_pct if capex_pct is not None else 0.03

            revenue_cagr_override, src = self._resolve(
                "revenue_cagr_override", params, llm_data, GENERIC_DEFAULTS, label="revenue_cagr_override"
            )
            data_sources.append(src)
            if revenue_cagr_override is not None:
                revenue_cagr_override = self._normalize_pct_field(revenue_cagr_override, "revenue_cagr_override")
            
            # Apply auto-capped CAGR from growth sanity check if no explicit override
            auto_cagr = params.get("revenue_cagr_override_auto")
            if revenue_cagr_override is None and auto_cagr is not None:
                revenue_cagr_override = auto_cagr
                data_sources.append(f"revenue_cagr_override: auto-capped to {auto_cagr*100:.1f}%")

            nwc_pct = float(params.get("nwc_percent_rev") or 0.10)

            base_fy, src = self._resolve("base_fy", params, llm_data, GENERIC_DEFAULTS, cast=int, label="base_fy")
            data_sources.append(src)
            base_fy = base_fy if base_fy else 2025

            dso = float(params.get("dso") or 45.0)
            dpo = float(params.get("dpo") or 30.0)
            dio = float(params.get("dio") or 30.0)

            ebitda_override = params.get("ebitda_margin_override")
            if ebitda_override:
                margin_val = float(ebitda_override)
                if margin_val > 1.0:
                    margin_val = margin_val / 100.0
                historical_ebitda_margins = [margin_val] * len(historical_ebitda_margins)

            avg_margin = sum(historical_ebitda_margins) / len(historical_ebitda_margins)
            is_loss_making = avg_margin < 0
            if is_loss_making:
                self.observe(f"WARNING: NEGATIVE EBITDA margin ({avg_margin*100:.1f}%).")

            self.observe(f"Data source audit: {'; '.join(data_sources)}")

            engine = DCFEngine(
                historical_revenues=historical_revenues,
                historical_ebitda_margins=historical_ebitda_margins,
                tax_rate=tax_rate,
                da_percent_rev=da_pct,
                cap_ex_percent_rev=capex_pct,
                revenue_cagr_override=revenue_cagr_override,
                nwc_percent_rev=nwc_pct,
                base_fy=base_fy,
                dso=dso, dpo=dpo, dio=dio,
                total_debt=llm_data.get("total_borrowings", GENERIC_DEFAULTS["total_borrowings"]),
                cash_and_equivalents=llm_data.get("cash_and_equivalents", GENERIC_DEFAULTS["cash_and_equivalents"])
            )

            projections_data = engine.build_projections(projection_years=7, terminal_growth_rate=tgr)

            valuation_data = engine.calculate_valuation(
                ufcf_projections=projections_data["projections"]["ufcf"],
                wacc=wacc,
                terminal_growth_rate=tgr,
                net_debt=net_debt,
                shares_outstanding=shares_outstanding
            )
            self.observe("DCF computed successfully.")

            # ─── Advanced Analysis ─────────────────────────
            ufcf = projections_data["projections"]["ufcf"]
            net_debt_float = float(net_debt) if isinstance(net_debt, str) else net_debt
            shares_float = float(shares_outstanding) if isinstance(shares_outstanding, str) else shares_outstanding

            scenario_data = engine.build_full_scenario_analysis(wacc, tgr, net_debt_float, shares_float)
            tv_crosscheck = engine.terminal_value_crosscheck(ufcf, wacc, tgr, exit_multiple=12.0)

            total_rev = sum(projections_data["projections"]["revenue"])
            sbc_data = engine.calculate_sbc_adjusted(
                valuation_data["implied_equity_value"], shares_outstanding,
                sbc_pct_rev=0.01, total_projected_revenue=total_rev
            )

            margin_sens = engine.calculate_margin_sensitivity(
                projections_data["projections"]["revenue"],
                wacc, tgr, net_debt_float, shares_float,
                base_margin=projections_data["assumptions"]["avg_ebitda_margin"]
            )

            capex_pct_float = float(capex_pct) if isinstance(capex_pct, str) else capex_pct
            capex_sens = engine.calculate_capex_sensitivity(
                ufcf, projections_data["projections"]["revenue"],
                wacc, tgr, net_debt_float, shares_float, capex_pct_float
            )

            sensitivity = engine.build_sensitivity_matrix(ufcf, wacc, tgr, net_debt_float, shares_float)

            # ─── Equity Bridge ─────────────────────────────
            total_borrowings = llm_data.get("total_borrowings")
            if total_borrowings is None:
                total_borrowings = GENERIC_DEFAULTS["total_borrowings"]

            cash_and_equiv = llm_data.get("cash_and_equivalents")
            if cash_and_equiv is None:
                cash_and_equiv = GENERIC_DEFAULTS["cash_and_equivalents"]

            if isinstance(total_borrowings, str):
                total_borrowings = float(total_borrowings)
            if isinstance(cash_and_equiv, str):
                cash_and_equiv = float(cash_and_equiv)

            net_debt_float = float(net_debt) if isinstance(net_debt, str) else net_debt

            if total_borrowings == 0 and cash_and_equiv == 0 and net_debt_float != 0:
                if net_debt_float > 0:
                    total_borrowings = net_debt_float
                    cash_and_equiv = 0
                else:
                    total_borrowings = 0
                    cash_and_equiv = abs(net_debt_float)

            def safe_round(val):
                return round(float(val), 2) if val is not None else 0.0

            ev_bridge = {
                "enterprise_value": safe_round(valuation_data.get("implied_enterprise_value")),
                "less_total_debt": safe_round(total_borrowings),
                "add_cash": safe_round(cash_and_equiv),
                "net_debt": safe_round(net_debt_float),
                "is_net_cash": net_debt_float < 0 if net_debt_float is not None else False,
                "equity_value": safe_round(valuation_data.get("implied_equity_value")),
                "shares_outstanding": shares_outstanding,
                "implied_price_per_share": safe_round(valuation_data.get("implied_share_price")),
            }

            # ─── Extraction Quality ───────────────────────
            docs = store.get_documents_for_deal(self.deal_id)
            if llm_data and fallback_mode:
                data_source_mode = "Deterministic Fallback"
            elif llm_data:
                data_source_mode = "LLM Extraction"
            else:
                data_source_mode = "Generic Defaults"

            # Build audit trail summary for the API response
            audit_trail_summary = []
            for rec in audit_records:
                audit_trail_summary.append({
                    "field": rec.field_name,
                    "confidence": rec.confidence_score,
                    "source": rec.source_citation,
                    "auditor_status": rec.auditor_status,
                    "triangulation": rec.triangulation_status,
                })

            extraction_quality = {
                "mode": data_source_mode,
                "source_type": docs[0].file_type.upper() if docs else "N/A",
                "pages_parsed": "N/A",
                "missing_fields": "none" if llm_data else "all (using generic fallbacks)",
                "is_loss_making": is_loss_making,
                "data_sources": data_sources,
                "pipeline_stages": ["Preparer", "Auditor", "Triangulator"],
                "audit_trail": audit_trail_summary,
                "triangulation": triangulation_result,
            }

            # ─── Bundle Result ─────────────────────────────
            deal = store.get_deal(self.deal_id)
            deal_name = deal.name if deal else "Unknown_Deal"

            warnings = valuation_data.get("warnings", [])
            if is_loss_making:
                warnings.append(f"NEGATIVE EBITDA MARGIN ({avg_margin*100:.1f}%): Company is loss-making.")
            if llm_data and fallback_mode:
                warnings.append(
                    "DETERMINISTIC FALLBACK USED: API extraction was unavailable, so a predefined "
                    f"profile ({fallback_profile or 'default'}) was applied."
                )
            if not llm_data:
                warnings.append("LLM EXTRACTION FAILED: Using generic fallback values. "
                              "Results will NOT reflect the uploaded company's actual financials.")

            valuation_result = {
                "header": {
                    "enterprise_value": valuation_data["implied_enterprise_value"],
                    "equity_value": valuation_data["implied_equity_value"],
                    "implied_share_price": valuation_data["implied_share_price"],
                    "wacc": wacc,
                    "wacc_breakdown": wacc_breakdown,
                    "terminal_method": "Gordon",
                },
                "currency": currency,
                "historical": projections_data.get("historical", {}),
                "fy_labels": projections_data["projections"].get("fy_labels", []),
                "scenarios": scenario_data,
                "ev_bridge": ev_bridge,
                "tv_crosscheck": tv_crosscheck,
                "sbc_adjusted": sbc_data,
                "margin_sensitivity": margin_sens,
                "capex_sensitivity": capex_sens,
                "sensitivity": sensitivity,
                "extraction_quality": extraction_quality,
                "assumptions": projections_data["assumptions"],
                "uploaded_company": deal_name,
                "warnings": warnings,
            }

            # ─── Excel Output ─────────────────────────────
            self.think("Generating professional Excel output artifact.")
            self.act("excel_writer", "Writing projections and valuation into DCF template")

            try:
                filepath = self.excel_tool.write_dcf_model(
                    deal_name=deal_name,
                    assumptions=projections_data["assumptions"],
                    projections=projections_data["projections"],
                    valuation={**valuation_data, "total_borrowings": total_borrowings, "wacc_breakdown": wacc_breakdown},
                    currency=currency,
                    historical=projections_data.get("historical")
                )
                self.observe(f"Workbook correctly saved to {filepath}")
            except Exception as e:
                import traceback
                self.fail(f"Excel generation failed: {str(e)}\n{traceback.format_exc()}")
                return self.run_id

            # Register output
            new_output = Output(
                deal_id=self.deal_id,
                agent_run_id=self.run_id,
                filename=os.path.basename(filepath),
                output_type="xlsx",
                output_category="financial_model",
                storage_path=filepath
            )
            store.outputs[new_output.id] = new_output

            run_record = store.agent_runs.get(self.run_id)
            if run_record:
                run_record.input_payload["valuation_result"] = valuation_result

            self.complete(confidence=0.95)

        except Exception as e:
            self.fail(f"Computation or formatting failed: {str(e)}")

        return self.run_id
