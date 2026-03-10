from typing import Dict, Any, List, Optional, Tuple
import json
import re
import time
import os

from agents.base import BaseAgent
from agents.prompt_builder import PromptBuilder
from engine.dcf import DCFEngine
from engine.llm import ask_llm
from tools.excel_writer import WorkbookBuilder
from store import store, Output


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
    # LLM Response Normalization — the key fix!
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(raw: str) -> dict:
        """
        Robustly parse LLM response that may contain markdown, thinking
        blocks, or extra text around the JSON.
        """
        text = raw.strip()

        # Strip DeepSeek <think>...</think> blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # Strip markdown fences
        text = text.replace('```json', '').replace('```', '').strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find first { ... last } and try to extract JSON
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
        """
        Auto-detect revenue units and convert to absolute INR.

        LLMs often return revenues in crores (e.g. 2789.61) or lakhs
        instead of absolute INR (27,896,100,000).

        Heuristics:
        - If max value < 100,000 → likely in Crores, multiply by 1e7
        - If max value < 10,000,000 → likely in Lakhs, multiply by 1e5
        - Otherwise → already absolute INR
        """
        if not revs or not all(isinstance(r, (int, float)) for r in revs):
            return revs

        max_val = max(revs)

        if max_val < 100_000:
            # Values like 2789.61 or 2500 → in Crores
            return [r * 1e7 for r in revs]
        elif max_val < 10_000_000:
            # Values like 278961 → in Lakhs
            return [r * 1e5 for r in revs]
        else:
            # Already in absolute numbers
            return revs

    @staticmethod
    def _normalize_margins(margins: list) -> list:
        """
        Auto-detect whether margins are decimals or percentages.

        LLMs often return 13.69 instead of 0.1369.

        Heuristic: if any |value| > 1.0, treat all as percentages and /100.
        """
        if not margins or not all(isinstance(m, (int, float)) for m in margins):
            return margins

        if any(abs(m) > 1.0 for m in margins):
            return [m / 100.0 for m in margins]
        return margins

    @staticmethod
    def _normalize_shares(shares) -> float:
        """
        Auto-detect shares unit and convert to absolute number.

        LLMs often return shares in crores (24.89) or millions (248.9)
        instead of absolute (248,900,000).

        Heuristics:
        - < 1,000       → in Crores, multiply by 1e7
        - < 100,000     → in Lakhs, multiply by 1e5
        - < 10,000,000  → in Millions, keep as-is or multiply by 1e6
        - Otherwise     → already absolute
        """
        if not isinstance(shares, (int, float)) or shares <= 0:
            return shares

        if shares < 1_000:
            # 24.89 → 24.89 Crore → 248,900,000
            return shares * 1e7
        elif shares < 100_000:
            # 24890 → 24,890 (way too small for shares, probably in lakhs)
            return shares * 1e5
        elif shares < 1_000_000:
            # 248900 → still small, probably in lakhs
            return shares * 100
        else:
            # Already absolute: 248900000
            return shares

    @staticmethod
    def _normalize_pct_field(val, field_name: str = "") -> float:
        """
        Normalize a percentage field that might be 4.0 (percent) vs 0.04 (decimal).
        Fields like cap_ex_percent_rev, da_percent_rev should be 0.0-0.5 range.
        """
        if not isinstance(val, (int, float)):
            return val
        if val > 1.0:
            # 4.0 → 0.04, 8.0 → 0.08
            return val / 100.0
        return val

    @staticmethod
    def _normalize_net_debt(val) -> float:
        """
        Normalize net_debt: if it looks like crores (small number), convert.
        """
        if not isinstance(val, (int, float)):
            return val
        if abs(val) < 100_000 and val != 0:
            # Likely in crores
            return val * 1e7
        return val

    @staticmethod
    def _to_number(val) -> Optional[float]:
        """Best-effort numeric coercion for JSON values that may arrive as strings."""
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
        """
        Keep debt assumptions internally consistent.
        Priority:
        1. If borrowings and cash exist, net_debt = borrowings - cash.
        2. If borrowings are zero/nil, debt_to_equity must be 0.
        """
        if not llm_data:
            return llm_data

        data = dict(llm_data)
        borrowings = cls._to_number(data.get("total_borrowings"))
        cash = cls._to_number(data.get("cash_and_equivalents"))
        net_debt = cls._to_number(data.get("net_debt"))
        debt_to_equity = cls._to_number(data.get("debt_to_equity"))

        if borrowings is not None and cash is not None:
            implied_net_debt = borrowings - cash
            data["net_debt"] = implied_net_debt
            if borrowings <= 0:
                data["debt_to_equity"] = 0.0
        elif borrowings is not None and borrowings <= 0:
            data["debt_to_equity"] = 0.0
            if net_debt is not None and net_debt > 0:
                data["net_debt"] = 0.0

        if debt_to_equity is not None and debt_to_equity > 0 and borrowings is not None and borrowings <= 0:
            data["debt_to_equity"] = 0.0

        return data

    # ------------------------------------------------------------------
    # Main Agent Logic
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
        prompt = PromptBuilder.build_modeling_dcf_prompt(params, context_header + context)

        # ═══════════════════════════════════════════════════════════════
        # GENERIC FALLBACK DEFAULTS — Used ONLY when LLM extraction
        # fails AND no user overrides provided.
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

        # ─── LLM Extraction ───────────────────────────────────
        llm_data = {}
        fallback_mode = False
        fallback_profile = ""
        self.act("llm_inference", "Sending VDR context to Gemini 2.5 Flash for parameter extraction")
        try:
            raw_response = ask_llm(self.system_prompt, prompt)
            self.observe(f"Raw LLM response (first 500 chars): {raw_response[:500]}")
            llm_data = self._parse_llm_response(raw_response)
            fallback_mode = str(llm_data.get("extraction_mode", "")).lower() == "deterministic_fallback"
            fallback_profile = str(llm_data.get("fallback_profile", ""))
            self.observe(f"LLM extraction parsed: {json.dumps(llm_data)}")
        except Exception as e:
            self.observe(f"LLM extraction failed ({str(e)}). Will use generic defaults.")
            llm_data = {}

        # ─── NORMALIZE LLM DATA (the critical fix!) ───────────
        if llm_data:
            # Revenues: auto-detect crores/lakhs/absolute
            if llm_data.get("historical_revenues"):
                raw_revs = llm_data["historical_revenues"]
                llm_data["historical_revenues"] = self._normalize_revenues(raw_revs)
                if raw_revs != llm_data["historical_revenues"]:
                    self.observe(f"Auto-normalized revenues: {raw_revs} → {llm_data['historical_revenues']}")

            # EBITDA margins: auto-detect percentages vs decimals
            if llm_data.get("historical_ebitda_margins"):
                raw_margins = llm_data["historical_ebitda_margins"]
                llm_data["historical_ebitda_margins"] = self._normalize_margins(raw_margins)
                if raw_margins != llm_data["historical_ebitda_margins"]:
                    self.observe(f"Auto-normalized margins: {raw_margins} → {llm_data['historical_ebitda_margins']}")

            # Shares outstanding: auto-detect crores/millions/absolute
            if llm_data.get("shares_outstanding"):
                raw_shares = llm_data["shares_outstanding"]
                llm_data["shares_outstanding"] = self._normalize_shares(raw_shares)
                if raw_shares != llm_data["shares_outstanding"]:
                    self.observe(f"Auto-normalized shares: {raw_shares} → {llm_data['shares_outstanding']}")

            # Net debt: auto-detect crores/absolute
            if llm_data.get("net_debt") is not None:
                raw_nd = llm_data["net_debt"]
                llm_data["net_debt"] = self._normalize_net_debt(raw_nd)

            # CapEx, D&A as percentages: auto-detect 4.0 vs 0.04
            for pct_field in ["cap_ex_percent_rev", "da_percent_rev"]:
                if llm_data.get(pct_field) is not None:
                    raw_val = llm_data[pct_field]
                    llm_data[pct_field] = self._normalize_pct_field(raw_val, pct_field)
                    if raw_val != llm_data[pct_field]:
                        self.observe(f"Auto-normalized {pct_field}: {raw_val} → {llm_data[pct_field]}")

            # Total borrowings / cash: normalize from crores if needed
            for debt_field in ["total_borrowings", "cash_and_equivalents"]:
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
            # Sanity: list of 2+ numbers, each > ₹10 Cr (100M) after normalization
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
            # After normalization, margins should be decimals in -2.0 to 0.99
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

        # ─── DCF Computation ───────────────────────────────────
        self.think("Engaging deterministic DCF Computation Engine.")
        self.act("python_exec", "Instantiating DCFEngine and calculating WACC/UFCF")
        try:
            tgr = params.get("terminal_growth_rate", 0.025)

            # WACC components
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

            # Net Debt
            net_debt, src = self._resolve("net_debt", params, llm_data, GENERIC_DEFAULTS, label="net_debt")
            data_sources.append(src)
            net_debt = net_debt if net_debt is not None else 0

            # Shares Outstanding
            shares_outstanding, src = self._resolve("shares_outstanding", params, llm_data, GENERIC_DEFAULTS, label="shares_outstanding")
            data_sources.append(src)
            shares_outstanding = shares_outstanding if shares_outstanding else 100_000_000

            # Engine operating parameters
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

            nwc_pct = float(params.get("nwc_percent_rev") or 0.10)

            base_fy, src = self._resolve("base_fy", params, llm_data, GENERIC_DEFAULTS, cast=int, label="base_fy")
            data_sources.append(src)
            base_fy = base_fy if base_fy else 2025

            dso = float(params.get("dso") or 45.0)
            dpo = float(params.get("dpo") or 30.0)
            dio = float(params.get("dio") or 30.0)

            # EBITDA margin override from frontend
            ebitda_override = params.get("ebitda_margin_override")
            if ebitda_override:
                margin_val = float(ebitda_override)
                if margin_val > 1.0:
                    margin_val = margin_val / 100.0  # User entered percentage
                historical_ebitda_margins = [margin_val] * len(historical_ebitda_margins)

            # Loss-making check
            avg_margin = sum(historical_ebitda_margins) / len(historical_ebitda_margins)
            is_loss_making = avg_margin < 0
            if is_loss_making:
                self.observe(f"WARNING: NEGATIVE EBITDA margin ({avg_margin*100:.1f}%).")

            # Log data sources
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
            extraction_quality = {
                "mode": data_source_mode,
                "source_type": docs[0].file_type.upper() if docs else "N/A",
                "pages_parsed": "N/A",
                "missing_fields": "none" if llm_data else "all (using generic fallbacks)",
                "is_loss_making": is_loss_making,
                "data_sources": data_sources,
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
