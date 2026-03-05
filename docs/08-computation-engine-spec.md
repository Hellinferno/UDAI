# 08 — Computation Logic Engine Spec
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

The **Computation Logic Engine (CLE)** is the deterministic calculation layer that sits between the LLM and the output formatters. The LLM produces *intent and structure* (which numbers to compute, what formula to apply, how to organize the output). The CLE performs the *actual arithmetic* using validated Python financial logic — ensuring accuracy, reproducibility, and protection against LLM hallucination on numerical outputs.

**Core Principle:**  
> The LLM decides *what* to compute. The CLE *computes it*.

---

## 2. Engine Architecture

```
LLM Output (structured JSON)
        ↓
[Input Validator]
   - Schema validation
   - Type coercion
   - Range checks
        ↓
[Computation Router]
   - Identifies model type: DCF / LBO / CCA / Other
        ↓
┌─────────────────────────────────────────────────┐
│         Computation Modules                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  DCF     │  │  LBO     │  │   CCA        │  │
│  │  Engine  │  │  Engine  │  │   Engine     │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────────────────┐  ┌─────────────────┐  │
│  │  Accretion/Dilution  │  │  Returns Calc   │  │
│  │  Engine              │  │  Engine         │  │
│  └──────────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────┘
        ↓
[Output Verifier]
   - Cross-check against source documents
   - Confidence scoring
   - Flag anomalies
        ↓
[Structured Output JSON]
   → Excel Writer / PDF Generator
```

---

## 3. Module 1: DCF (Discounted Cash Flow) Engine

### 3.1 Inputs Schema

```python
@dataclass
class DCFInputs:
    # Revenue Projections
    historical_revenue: list[float]          # Last 3-5 years of revenue
    revenue_growth_rates: list[float]         # % growth per projection year (LLM-suggested or user-set)
    projection_years: int = 5                 # Typically 5
    
    # Margin Assumptions
    ebitda_margins: list[float]               # EBITDA margin per year
    da_percent_revenue: float                 # D&A as % of revenue
    capex_percent_revenue: float             # CapEx as % of revenue
    nwc_change_percent_revenue: float        # Change in NWC as % of revenue
    
    # Tax and Capital Structure
    tax_rate: float = 0.25
    
    # WACC Components
    risk_free_rate: float                    # e.g., 0.045 (10-yr US Treasury)
    equity_risk_premium: float = 0.055       # Historical ERP
    beta: float = 1.0                        # Levered beta
    cost_of_debt: float                      # Pre-tax
    debt_to_capital: float                   # Target capital structure
    
    # Terminal Value
    terminal_growth_rate: float = 0.025      # Gordon Growth terminal value
    # OR
    exit_multiple: float = None              # EV/EBITDA exit multiple (alternative)
    
    # Net Debt and Shares
    net_debt: float = 0.0
    shares_outstanding: float = 1.0
```

### 3.2 Computation Steps

```python
class DCFEngine:
    """
    Deterministic DCF computation engine.
    All formulas are standard IB methodology.
    """
    
    def compute(self, inputs: DCFInputs) -> DCFOutputs:
        # Step 1: Project Revenue
        revenues = self._project_revenues(
            base=inputs.historical_revenue[-1],
            growth_rates=inputs.revenue_growth_rates,
            years=inputs.projection_years
        )
        
        # Step 2: Project EBITDA
        ebitda = [rev * margin for rev, margin in zip(revenues, inputs.ebitda_margins)]
        
        # Step 3: Project EBIT
        da = [rev * inputs.da_percent_revenue for rev in revenues]
        ebit = [e - d for e, d in zip(ebitda, da)]
        
        # Step 4: Compute NOPAT (Net Operating Profit After Tax)
        nopat = [e * (1 - inputs.tax_rate) for e in ebit]
        
        # Step 5: Compute Unlevered Free Cash Flow (UFCF)
        capex = [rev * inputs.capex_percent_revenue for rev in revenues]
        delta_nwc = [rev * inputs.nwc_change_percent_revenue for rev in revenues]
        ufcf = [
            nopat[i] + da[i] - capex[i] - delta_nwc[i]
            for i in range(inputs.projection_years)
        ]
        
        # Step 6: Compute WACC
        wacc = self._compute_wacc(inputs)
        
        # Step 7: Discount UFCF to Present Value
        pv_ufcfs = [
            ufcf[i] / ((1 + wacc) ** (i + 1))
            for i in range(inputs.projection_years)
        ]
        sum_pv_ufcf = sum(pv_ufcfs)
        
        # Step 8: Compute Terminal Value
        if inputs.exit_multiple:
            # Exit multiple method
            terminal_ebitda = ebitda[-1]
            terminal_value = terminal_ebitda * inputs.exit_multiple
        else:
            # Gordon Growth Model
            terminal_fcf = ufcf[-1] * (1 + inputs.terminal_growth_rate)
            terminal_value = terminal_fcf / (wacc - inputs.terminal_growth_rate)
        
        pv_terminal_value = terminal_value / ((1 + wacc) ** inputs.projection_years)
        
        # Step 9: Enterprise Value
        enterprise_value = sum_pv_ufcf + pv_terminal_value
        
        # Step 10: Equity Value and Implied Share Price
        equity_value = enterprise_value - inputs.net_debt
        implied_share_price = equity_value / inputs.shares_outstanding if inputs.shares_outstanding > 0 else 0
        
        # Step 11: Football Field (sensitivity table)
        sensitivity = self._build_sensitivity_table(
            inputs=inputs,
            wacc_range=(-0.02, 0.02, 0.005),          # WACC ± 2%, step 0.5%
            tgr_range=(-0.01, 0.01, 0.005)             # TGR ± 1%, step 0.5%
        )
        
        return DCFOutputs(
            revenues=revenues,
            ebitda=ebitda,
            ufcf=ufcf,
            wacc=wacc,
            pv_ufcfs=pv_ufcfs,
            sum_pv_ufcf=sum_pv_ufcf,
            terminal_value=terminal_value,
            pv_terminal_value=pv_terminal_value,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            implied_share_price=implied_share_price,
            sensitivity_table=sensitivity
        )
    
    def _compute_wacc(self, inputs: DCFInputs) -> float:
        """WACC = Ke * E/V + Kd * (1 - t) * D/V"""
        ke = inputs.risk_free_rate + inputs.beta * inputs.equity_risk_premium  # CAPM
        equity_weight = 1 - inputs.debt_to_capital
        debt_weight = inputs.debt_to_capital
        wacc = (ke * equity_weight) + (inputs.cost_of_debt * (1 - inputs.tax_rate) * debt_weight)
        return wacc
    
    def _project_revenues(self, base: float, growth_rates: list[float], years: int) -> list[float]:
        revenues = []
        current = base
        for i in range(years):
            current = current * (1 + growth_rates[i])
            revenues.append(current)
        return revenues
    
    def _build_sensitivity_table(self, inputs, wacc_range, tgr_range) -> dict:
        """Builds a 2-D sensitivity matrix of enterprise value by WACC and TGR."""
        start_w, end_w, step_w = wacc_range
        start_t, end_t, step_t = tgr_range
        base_wacc = self._compute_wacc(inputs)
        
        wacc_scenarios = [base_wacc + x for x in self._frange(start_w, end_w, step_w)]
        tgr_scenarios = [inputs.terminal_growth_rate + x for x in self._frange(start_t, end_t, step_t)]
        
        table = {}
        for wacc_s in wacc_scenarios:
            table[round(wacc_s, 4)] = {}
            for tgr_s in tgr_scenarios:
                # Recalculate EV with scenario WACC and TGR
                ev = self._ev_for_scenario(inputs, wacc_s, tgr_s)
                table[round(wacc_s, 4)][round(tgr_s, 4)] = round(ev, 2)
        
        return table
```

---

## 4. Module 2: LBO Engine

### 4.1 Inputs Schema

```python
@dataclass
class LBOInputs:
    # Entry
    entry_ebitda: float
    entry_multiple: float                     # EV/EBITDA at purchase
    management_rollover_percent: float = 0.0  # % of equity from management
    
    # Debt Structure (Sources & Uses)
    senior_debt_multiple: float = 3.0         # x EBITDA
    senior_debt_rate: float = 0.07
    subordinated_debt_multiple: float = 1.0   # x EBITDA
    sub_debt_rate: float = 0.12
    
    # Operating Assumptions
    revenue_growth_rates: list[float]
    ebitda_margins: list[float]
    capex_percent_revenue: float = 0.03
    nwc_change_percent_revenue: float = 0.02
    tax_rate: float = 0.25
    projection_years: int = 5
    
    # Exit
    exit_multiple: float                      # EV/EBITDA at sale
```

### 4.2 Key Outputs

```python
@dataclass
class LBOOutputs:
    # Sources & Uses
    purchase_price: float
    total_debt: float
    equity_check: float
    sources_uses_table: dict
    
    # Returns
    exit_enterprise_value: float
    exit_equity_value: float
    gross_irr: float                          # Annualized
    moic: float                               # Multiple on Invested Capital
    
    # Debt Schedule (per year)
    debt_schedule: list[dict]                 # {year, senior_balance, sub_balance, interest_expense, cash_sweep}
    
    # Income Statement (projected)
    income_statement: list[dict]
```

### 4.3 IRR Calculation

```python
def compute_irr(self, equity_invested: float, equity_at_exit: float, years: int) -> float:
    """
    MOIC = equity_at_exit / equity_invested
    IRR = MOIC^(1/years) - 1
    (Simplified for constant-hold-period. Full IRR uses numpy.irr for irregular cash flows.)
    """
    import numpy as np
    moic = equity_at_exit / equity_invested
    irr = moic ** (1 / years) - 1
    return irr
```

---

## 5. Module 3: Comparable Company Analysis (CCA) Engine

### 5.1 Data Schema

```python
@dataclass
class ComparableCompany:
    name: str
    ticker: str
    enterprise_value: float
    equity_value: float
    revenue_ltm: float                        # Last Twelve Months
    ebitda_ltm: float
    ebit_ltm: float
    net_income_ltm: float
    
    # Derived multiples (computed by engine)
    ev_revenue: float = None
    ev_ebitda: float = None
    ev_ebit: float = None
    pe_ratio: float = None
    
@dataclass
class CCAOutputs:
    comparables: list[ComparableCompany]
    median_ev_ebitda: float
    mean_ev_ebitda: float
    median_ev_revenue: float
    mean_ev_revenue: float
    implied_target_ev_low: float              # Using 25th percentile
    implied_target_ev_high: float             # Using 75th percentile
    implied_target_ev_median: float
```

### 5.2 Multiple Computation

```python
class CCAEngine:
    def compute(self, comparables_raw: list[dict], target_ebitda: float, target_revenue: float) -> CCAOutputs:
        comps = []
        for c in comparables_raw:
            comp = ComparableCompany(**c)
            comp.ev_revenue = comp.enterprise_value / comp.revenue_ltm if comp.revenue_ltm else None
            comp.ev_ebitda = comp.enterprise_value / comp.ebitda_ltm if comp.ebitda_ltm else None
            comp.ev_ebit = comp.enterprise_value / comp.ebit_ltm if comp.ebit_ltm else None
            comp.pe_ratio = comp.equity_value / comp.net_income_ltm if comp.net_income_ltm else None
            comps.append(comp)
        
        ev_ebitda_values = [c.ev_ebitda for c in comps if c.ev_ebitda]
        
        import statistics
        median_ev_ebitda = statistics.median(ev_ebitda_values)
        
        # Implied EV for target
        implied_ev_median = median_ev_ebitda * target_ebitda
        
        return CCAOutputs(
            comparables=comps,
            median_ev_ebitda=median_ev_ebitda,
            mean_ev_ebitda=statistics.mean(ev_ebitda_values),
            median_ev_revenue=statistics.median([c.ev_revenue for c in comps if c.ev_revenue]),
            mean_ev_revenue=statistics.mean([c.ev_revenue for c in comps if c.ev_revenue]),
            implied_target_ev_median=implied_ev_median,
            implied_target_ev_low=sorted(ev_ebitda_values)[len(ev_ebitda_values)//4] * target_ebitda,
            implied_target_ev_high=sorted(ev_ebitda_values)[3*len(ev_ebitda_values)//4] * target_ebitda,
        )
```

---

## 6. Hallucination Guard

The Hallucination Guard is a post-computation verification module that cross-references LLM-suggested inputs against uploaded financial documents.

### 6.1 Verification Rules

```python
class HallucinationGuard:
    """
    Compares LLM-extracted financial figures against source document parsed text.
    Flags discrepancies above threshold.
    """
    
    TOLERANCE_PERCENT = 0.05  # 5% variance allowed
    
    def verify(self, llm_inputs: dict, source_parsed_texts: list[str]) -> VerificationResult:
        flags = []
        
        # Extract all numbers from source documents
        source_numbers = self._extract_numbers_from_text(source_parsed_texts)
        
        # Check each key financial figure
        for field, value in llm_inputs.items():
            if isinstance(value, (int, float)):
                is_verified = self._check_number_in_sources(value, source_numbers)
                if not is_verified:
                    flags.append(HallucinationFlag(
                        field=field,
                        llm_value=value,
                        severity="high" if "revenue" in field or "ebitda" in field else "medium",
                        message=f"Value {value} for '{field}' not found in source documents"
                    ))
        
        confidence = 1.0 - (len(flags) / max(len(llm_inputs), 1)) * 0.5
        
        return VerificationResult(
            is_clean=len([f for f in flags if f.severity == "high"]) == 0,
            confidence_score=round(confidence, 2),
            flags=flags
        )
    
    def _check_number_in_sources(self, value: float, source_numbers: list[float]) -> bool:
        for src_val in source_numbers:
            if abs(value - src_val) / max(abs(src_val), 1) <= self.TOLERANCE_PERCENT:
                return True
        return False
```

---

## 7. Output Verification Checklist

Before any financial model is presented to the user, the engine runs these checks:

| Check | Description | Action if Failed |
|---|---|---|
| Balance check | Assets = Liabilities + Equity | Flag "Balance sheet does not balance" |
| DCF sanity | WACC > terminal growth rate | Flag "WACC must exceed terminal growth rate" |
| Positive EBITDA | EBITDA should not be negative in base case | Warning "Negative EBITDA in base case" |
| Revenue trend | Revenue projections should be monotonic if growth > 0 | Silent correction |
| LBO debt coverage | DSCR > 1.0x in all years | Flag "Debt service coverage concern" |
| IRR sanity | IRR between 0% and 100% | Flag "Unusual IRR — please review assumptions" |
| CCA count | At least 3 comparables | Warning "Fewer than 3 comparables — limited statistical reliability" |

---

*End of Document — 08-computation-engine-spec.md*
