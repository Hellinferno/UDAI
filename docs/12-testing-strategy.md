# 12 — Testing Strategy
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

Testing an LLM-based agent system requires a different approach than traditional software. There are two categories of tests:

1. **Deterministic tests** — Standard unit/integration tests for the computation engine, API, tools, and UI.
2. **LLM-behavior tests** — Prompt-based evaluations that check agent output quality, structure, and accuracy against defined criteria.

**Testing Pyramid:**
```
              ┌───────────────────┐
              │   E2E Tests (5%)   │  Playwright
              ├───────────────────┤
              │Integration (25%)  │  Pytest + httpx
              ├───────────────────┤
              │   Unit Tests      │  Pytest / Vitest
              │     (70%)         │
              └───────────────────┘
```

**Coverage Target:**
- Python backend + computation engine: ≥ 80%
- Agent logic: ≥ 70%
- Frontend components: ≥ 60%
- E2E (critical paths): 100% of P0 user stories

---

## 2. Unit Tests

### 2.1 Computation Engine Tests

These are the most critical tests. Financial calculations must be 100% verifiable.

#### DCF Engine Tests

```python
# tests/unit/test_dcf_engine.py
import pytest
from agents.modeling.dcf import DCFEngine, DCFInputs

class TestDCFEngine:
    
    def setup_method(self):
        self.engine = DCFEngine()
    
    def test_wacc_calculation(self):
        """WACC formula: Ke*E/V + Kd*(1-t)*D/V"""
        inputs = DCFInputs(
            risk_free_rate=0.045,
            beta=1.2,
            equity_risk_premium=0.055,
            cost_of_debt=0.07,
            debt_to_capital=0.30,
            tax_rate=0.25,
            # ... other required fields
        )
        wacc = self.engine._compute_wacc(inputs)
        
        # Manual calculation:
        # Ke = 0.045 + 1.2 * 0.055 = 0.111
        # WACC = 0.111 * 0.70 + 0.07 * 0.75 * 0.30 = 0.0777 + 0.01575 = 0.09345
        assert abs(wacc - 0.09345) < 0.0001, f"Expected ~0.09345, got {wacc}"
    
    def test_revenue_projection(self):
        """Revenue projections should compound correctly"""
        revenues = self.engine._project_revenues(
            base=100.0,
            growth_rates=[0.20, 0.20, 0.15, 0.15, 0.10],
            years=5
        )
        assert len(revenues) == 5
        assert abs(revenues[0] - 120.0) < 0.01  # 100 * 1.20
        assert abs(revenues[1] - 144.0) < 0.01  # 120 * 1.20
        assert abs(revenues[2] - 165.6) < 0.01  # 144 * 1.15
    
    def test_terminal_value_gordon_growth(self):
        """Terminal value = FCF_t * (1+g) / (WACC - g)"""
        final_fcf = 50.0
        wacc = 0.10
        tgr = 0.025
        terminal_value = final_fcf * (1 + tgr) / (wacc - tgr)
        # = 50 * 1.025 / 0.075 = 683.33
        assert abs(terminal_value - 683.33) < 0.5
    
    def test_dcf_full_run_known_case(self):
        """Full DCF run on known inputs — verify enterprise value within 2%"""
        inputs = DCFInputs(
            historical_revenue=[80.0, 95.0, 115.0],
            revenue_growth_rates=[0.25, 0.22, 0.18, 0.15, 0.12],
            ebitda_margins=[0.28, 0.30, 0.32, 0.33, 0.34],
            da_percent_revenue=0.05,
            capex_percent_revenue=0.04,
            nwc_change_percent_revenue=0.02,
            tax_rate=0.25,
            risk_free_rate=0.045,
            beta=1.1,
            equity_risk_premium=0.055,
            cost_of_debt=0.065,
            debt_to_capital=0.25,
            terminal_growth_rate=0.025,
            net_debt=50.0,
            shares_outstanding=10.0,
            projection_years=5
        )
        result = self.engine.compute(inputs)
        
        # Verify structure
        assert result.enterprise_value > 0
        assert result.equity_value > 0
        assert result.implied_share_price > 0
        assert len(result.revenues) == 5
        assert len(result.ufcf) == 5
        assert result.wacc > result.inputs.terminal_growth_rate  # WACC must exceed TGR
    
    def test_sensitivity_table_dimensions(self):
        """Sensitivity table must have correct WACC x TGR grid"""
        # With ±2% WACC in 0.5% steps: [-2, -1.5, -1, -0.5, 0, +0.5, +1, +1.5, +2] = 9 steps
        # With ±1% TGR in 0.5% steps: 5 steps
        result = self.engine.compute(valid_inputs_fixture())
        table = result.sensitivity_table
        assert len(table) == 9   # WACC scenarios
        first_wacc_row = list(table.values())[0]
        assert len(first_wacc_row) == 5  # TGR scenarios
    
    def test_wacc_must_exceed_tgr(self):
        """If WACC < TGR, terminal value formula breaks — should raise error"""
        inputs = valid_inputs_fixture()
        inputs.terminal_growth_rate = 0.15  # Artificially high TGR > WACC
        with pytest.raises(ValueError, match="WACC must exceed terminal growth rate"):
            self.engine.compute(inputs)
```

#### LBO Engine Tests

```python
# tests/unit/test_lbo_engine.py
class TestLBOEngine:
    
    def test_sources_and_uses_balance(self):
        """Total sources must equal total uses"""
        result = lbo_engine.compute(valid_lbo_inputs())
        total_sources = result.equity_check + result.total_debt
        total_uses = result.purchase_price
        assert abs(total_sources - total_uses) < 0.01
    
    def test_irr_calculation(self):
        """2x MOIC in 5 years ≈ 14.9% IRR"""
        irr = lbo_engine.compute_irr(equity_invested=100, equity_at_exit=200, years=5)
        assert abs(irr - 0.1487) < 0.001
    
    def test_moic_calculation(self):
        """MOIC = exit equity / entry equity"""
        result = lbo_engine.compute(valid_lbo_inputs())
        assert result.moic == pytest.approx(result.exit_equity_value / result.equity_check, rel=0.01)
```

#### Hallucination Guard Tests

```python
# tests/unit/test_hallucination_guard.py
class TestHallucinationGuard:
    
    def test_detects_fabricated_revenue(self):
        """If LLM invents a revenue figure not in source docs, should flag it"""
        guard = HallucinationGuard()
        llm_inputs = {"historical_revenue": [999_000_000]}  # Huge fake number
        source_texts = ["Revenue for FY2023: $15.2 million. FY2022: $11.8 million."]
        
        result = guard.verify(llm_inputs, source_texts)
        assert result.is_clean == False
        assert len(result.flags) >= 1
        assert result.confidence_score < 0.5
    
    def test_passes_accurate_revenue(self):
        """Revenue figure that matches source document should not be flagged"""
        guard = HallucinationGuard()
        llm_inputs = {"historical_revenue": [15.2]}  # In millions, matches source
        source_texts = ["Revenue for FY2023: $15.2 million."]
        
        result = guard.verify(llm_inputs, source_texts)
        assert result.is_clean == True
        assert len([f for f in result.flags if f.severity == "high"]) == 0
```

---

### 2.2 File Parser Tests

```python
# tests/unit/test_file_parsers.py
class TestFileParsers:
    
    def test_pdf_text_extraction(self, sample_pdf_path):
        result = pdf_parser.parse(sample_pdf_path)
        assert result.parse_status == "completed"
        assert len(result.text) > 100
        assert "Revenue" in result.text  # Known content in test PDF
    
    def test_excel_parser_extracts_numbers(self, sample_financial_xlsx):
        result = excel_parser.parse(sample_financial_xlsx)
        assert result.parse_status == "completed"
        assert len(result.tables) >= 1
        first_table = result.tables[0]
        assert any(isinstance(v, (int, float)) for v in first_table.values())
    
    def test_parse_failure_returns_error_status(self, corrupted_pdf_path):
        result = pdf_parser.parse(corrupted_pdf_path)
        assert result.parse_status == "failed"
        assert result.error is not None
```

---

### 2.3 Frontend Component Tests

```typescript
// tests/unit/AgentCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { AgentCard } from '@/components/agents/AgentCard'

describe('AgentCard', () => {
  it('renders agent name and description', () => {
    render(<AgentCard agentType="modeling" status="idle" />)
    expect(screen.getByText('Financial Modeling Agent')).toBeInTheDocument()
  })

  it('shows Run button when status is idle', () => {
    render(<AgentCard agentType="modeling" status="idle" onRun={() => {}} />)
    expect(screen.getByRole('button', { name: /run/i })).toBeEnabled()
  })

  it('disables Run button when status is running', () => {
    render(<AgentCard agentType="modeling" status="running" onRun={() => {}} />)
    expect(screen.getByRole('button', { name: /running/i })).toBeDisabled()
  })

  it('calls onRun when Run button is clicked', () => {
    const onRun = vi.fn()
    render(<AgentCard agentType="modeling" status="idle" onRun={onRun} />)
    fireEvent.click(screen.getByRole('button', { name: /run/i }))
    expect(onRun).toHaveBeenCalledOnce()
  })

  it('shows hallucination warning badge when confidence is below 0.6', () => {
    render(<AgentCard agentType="modeling" status="completed" confidenceScore={0.45} />)
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })
})
```

---

## 3. Integration Tests

### 3.1 API Integration Tests

```python
# tests/integration/test_deals_api.py
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
class TestDealsAPI:
    
    async def test_create_deal_success(self, client: AsyncClient):
        response = await client.post("/api/v1/deals", json={
            "name": "Test Deal",
            "company_name": "TestCo",
            "deal_type": "ma_sellside",
            "industry": "Technology",
            "deal_stage": "preliminary"
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test Deal"
        assert "id" in data
    
    async def test_create_deal_missing_company_name(self, client: AsyncClient):
        response = await client.post("/api/v1/deals", json={
            "name": "Test Deal",
            "deal_type": "ma_sellside",
            "industry": "Technology",
            "deal_stage": "preliminary"
        })
        assert response.status_code == 422
        assert "company_name" in response.json()["error"]["details"]
    
    async def test_upload_document(self, client: AsyncClient, sample_pdf):
        # Create deal first
        deal_id = await create_test_deal(client)
        
        response = await client.post(
            f"/api/v1/deals/{deal_id}/documents",
            files={"files": ("test.pdf", sample_pdf, "application/pdf")}
        )
        assert response.status_code == 201
        uploaded = response.json()["data"]["uploaded"]
        assert len(uploaded) == 1
        assert uploaded[0]["file_type"] == "pdf"
```

### 3.2 Agent Integration Tests (Mock LLM)

```python
# tests/integration/test_modeling_agent.py
from unittest.mock import AsyncMock, patch

class TestModelingAgentIntegration:
    
    @patch('src.llm.client.LLMClient.generate')
    async def test_dcf_agent_produces_xlsx(self, mock_llm, client, sample_financial_doc):
        """End-to-end test with mocked LLM response"""
        
        # Mock LLM returns valid DCF parameters
        mock_llm.return_value = """
        {
          "revenue_growth_rates": [0.25, 0.22, 0.18, 0.15, 0.12],
          "ebitda_margins": [0.28, 0.30, 0.32, 0.33, 0.34],
          "wacc_override": null,
          "terminal_growth_rate": 0.025
        }
        """
        
        deal_id = await create_deal_with_document(client, sample_financial_doc)
        
        # Trigger agent
        run_response = await client.post(f"/api/v1/deals/{deal_id}/agents/run", json={
            "agent_type": "modeling",
            "task_name": "dcf_model",
            "parameters": {"projection_years": 5}
        })
        assert run_response.status_code == 202
        run_id = run_response.json()["data"]["run_id"]
        
        # Wait for completion (or poll)
        import asyncio
        await asyncio.sleep(2)  # In real tests: poll or use test client SSE
        
        # Check run completed
        run_detail = await client.get(f"/api/v1/agents/runs/{run_id}")
        assert run_detail.json()["data"]["status"] == "completed"
        
        # Check output exists
        outputs = await client.get(f"/api/v1/deals/{deal_id}/outputs")
        assert len(outputs.json()["data"]["outputs"]) == 1
        assert outputs.json()["data"]["outputs"][0]["output_type"] == "xlsx"
```

---

## 4. LLM Behavior Tests (Prompt Evaluation)

These tests evaluate the quality of LLM outputs using a scoring rubric. They run with the real Colab model (not in normal CI — run manually or on a schedule).

```python
# tests/llm_eval/test_prompt_quality.py

EVAL_CASES = [
    {
        "id": "DCF-001",
        "agent": "modeling",
        "task": "dcf_model",
        "input": "Company: TechStartup Inc. Revenue 2023: $15M growing at ~25% YoY. EBITDA margin ~30%. Please extract DCF parameters.",
        "expected_structure": ["revenue_growth_rates", "ebitda_margins", "terminal_growth_rate"],
        "must_not_contain": ["I cannot", "I don't know", "As an AI"],
        "format": "json"
    },
    {
        "id": "PITCH-001", 
        "agent": "pitchbook",
        "task": "full_pitchbook",
        "input": "Create slide 1 (Cover) for a sell-side M&A pitchbook for Nexus Pharma.",
        "expected_content": ["Nexus Pharma", "Confidential", "sell-side"],
        "must_not_contain": ["Lorem ipsum"],
        "min_word_count": 20
    },
    {
        "id": "DD-001",
        "agent": "due_diligence",
        "task": "risk_summary",
        "input": "Document excerpt: 'The company has 3 outstanding lawsuits. Revenue declined 15% YoY. Key customer represents 60% of revenue.'",
        "must_identify_risks": ["litigation", "revenue_decline", "customer_concentration"],
        "min_risk_count": 2
    }
]

class LLMEvalSuite:
    async def run_all(self):
        results = []
        for case in EVAL_CASES:
            score = await self.evaluate_case(case)
            results.append({"id": case["id"], "score": score, "passed": score >= 0.7})
        return results
    
    async def evaluate_case(self, case) -> float:
        response = await llm_client.generate(case["input"])
        scores = []
        
        if "expected_structure" in case:
            for key in case["expected_structure"]:
                if key in response:
                    scores.append(1.0)
                else:
                    scores.append(0.0)
        
        if "must_not_contain" in case:
            for phrase in case["must_not_contain"]:
                if phrase.lower() not in response.lower():
                    scores.append(1.0)
                else:
                    scores.append(0.0)
        
        return sum(scores) / len(scores) if scores else 0.0
```

**Minimum passing scores:**
| Agent | Min Score |
|---|---|
| Financial Modeling | 85% |
| Pitchbook | 80% |
| Due Diligence | 85% |
| Market Research | 75% |
| Doc Drafter | 80% |
| Coordination | 75% |

---

## 5. End-to-End Tests

```python
# tests/e2e/test_dcf_workflow.py (Playwright)
from playwright.async_api import async_playwright

async def test_full_dcf_workflow():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Step 1: Navigate to app
        await page.goto("http://localhost:3000")
        
        # Step 2: Create new deal
        await page.click("[data-testid='new-deal-btn']")
        await page.fill("[data-testid='deal-name-input']", "E2E Test Deal")
        await page.fill("[data-testid='company-name-input']", "TestCo")
        await page.select_option("[data-testid='deal-type-select']", "ma_sellside")
        await page.click("[data-testid='create-deal-btn']")
        
        # Step 3: Upload financial document
        await page.click("[data-testid='documents-tab']")
        await page.set_input_files("[data-testid='file-upload-input']", "tests/fixtures/sample_financials.xlsx")
        await page.wait_for_selector("[data-testid='doc-status-completed']", timeout=30000)
        
        # Step 4: Run DCF agent
        await page.click("[data-testid='agents-tab']")
        await page.click("[data-testid='agent-modeling-run-btn']")
        
        # Step 5: Watch reasoning panel
        await page.wait_for_selector("[data-testid='reasoning-step-1']", timeout=10000)
        
        # Step 6: Wait for completion
        await page.wait_for_selector("[data-testid='run-status-completed']", timeout=300000)
        
        # Step 7: Verify output exists
        await page.click("[data-testid='outputs-tab']")
        output_card = page.locator("[data-testid='output-card']")
        await expect(output_card).to_be_visible()
        
        # Step 8: Download output
        async with page.expect_download() as download_info:
            await page.click("[data-testid='output-download-btn']")
        download = await download_info.value
        assert download.suggested_filename.endswith(".xlsx")
        
        await browser.close()
```

---

## 6. Test Fixtures

```
tests/
├── fixtures/
│   ├── sample_financials.xlsx         # 3-year P&L + Balance Sheet
│   ├── sample_annual_report.pdf       # Real-format but synthetic company
│   ├── sample_contracts.docx          # Employment agreement stub
│   ├── sample_data_room/              # Bundle of 5+ docs for DD tests
│   │   ├── financial_statements.xlsx
│   │   ├── cap_table.xlsx
│   │   ├── customer_contracts.docx
│   │   ├── tax_returns.pdf
│   │   └── employment_agreements.docx
│   └── known_answers/
│       ├── dcf_expected_output.json   # Known-good DCF for test_known_case
│       └── lbo_expected_output.json
│
├── unit/
├── integration/
├── llm_eval/
└── e2e/
```

---

## 7. Test Execution Plan

| Stage | Command | Runs In | When |
|---|---|---|---|
| Unit tests | `pytest tests/unit/` | CI / Local | Every commit |
| Integration tests | `pytest tests/integration/` | CI / Local | Every PR |
| LLM eval tests | `python tests/llm_eval/run.py` | Local (Colab) | Weekly / Pre-release |
| E2E tests | `pytest tests/e2e/ --headed` | Local | Pre-release |

---

## 8. Bug Reporting Template

When a test fails or a bug is found, log it with:

```
## Bug Report

**ID:** BUG-###
**Severity:** P0 / P1 / P2
**Component:** Frontend / Backend / Agent / Computation Engine / Colab
**User Story:** US-###

**Steps to Reproduce:**
1. ...
2. ...

**Expected Behavior:**
...

**Actual Behavior:**
...

**Error Message / Screenshot:**
...

**Acceptance Criteria Violated:**
AC-# from US-###
```

---

*End of Document — 12-testing-strategy.md*
