"""
The "Preparer" Agent — Financial Data Extractor with Chain-of-Thought Reconciliation.

Instead of a single "extract everything" prompt, this agent forces the LLM to:
1. Show step-by-step mathematical work (reconciliation schedule)
2. Cite the exact source text for every extracted number
3. Self-assess confidence per field (0.0 – 1.0)

This is the "Maker" in the Maker-Checker architecture.
"""
from typing import Dict, Any, List, Optional
import json
import re

from engine.llm import ask_llm
from agents.prompt_builder import PromptBuilder


class PreparerAgent:
    """
    Extracts financial data using chain-of-thought reconciliation prompting.
    Returns structured data with per-field confidence scores and source citations.
    """

    @classmethod
    def extract(cls, system_prompt: str, document_context: str,
                params: dict, company_name: str = "") -> Dict[str, Any]:
        """
        Run the Preparer extraction pipeline.

        Returns:
            {
                "extracted_data": { ... financial fields ... },
                "audit_trail": [
                    {
                        "field": "historical_revenues",
                        "value": [...],
                        "confidence": 0.92,
                        "source_citation": "Statement of P&L, Page 45",
                        "reasoning": "Revenue from Operations: ₹2,789.61 Cr (FY25)..."
                    },
                    ...
                ],
                "reconciliation_log": "Step-by-step EBITDA calculation...",
                "extraction_mode": "llm" | "deterministic_fallback"
            }
        """
        prompt = PromptBuilder.build_preparer_prompt(params, document_context, company_name)

        try:
            raw_response = ask_llm(system_prompt, prompt)
            parsed = cls._parse_preparer_response(raw_response)

            # Separate the audit trail from the raw data
            audit_trail = parsed.pop("audit_trail", [])
            reconciliation_log = parsed.pop("reconciliation_log", "")
            extraction_mode = parsed.pop("extraction_mode", "llm")

            # The remaining keys are the actual financial data
            extracted_data = {}
            for key, val in parsed.items():
                if isinstance(val, dict) and "value" in val:
                    # Structured field: {value, confidence, source}
                    extracted_data[key] = val["value"]
                    audit_trail.append({
                        "field": key,
                        "value": val["value"],
                        "confidence": val.get("confidence", 0.5),
                        "source_citation": val.get("source", "Not cited"),
                        "reasoning": val.get("reasoning", ""),
                    })
                else:
                    extracted_data[key] = val

            # Ensure every field in extracted_data has an audit entry
            audit_fields = {a["field"] for a in audit_trail}
            for key, val in extracted_data.items():
                if key not in audit_fields and key not in ("currency", "extraction_mode", "fallback_profile"):
                    audit_trail.append({
                        "field": key,
                        "value": val,
                        "confidence": 0.5 if val is not None else 0.0,
                        "source_citation": "Extracted without explicit citation",
                        "reasoning": "",
                    })

            return {
                "extracted_data": extracted_data,
                "audit_trail": audit_trail,
                "reconciliation_log": reconciliation_log,
                "extraction_mode": extraction_mode,
            }

        except Exception as e:
            print(f"[Preparer] Extraction failed: {e}")
            return {
                "extracted_data": {},
                "audit_trail": [],
                "reconciliation_log": f"Extraction failed: {str(e)}",
                "extraction_mode": "failed",
            }

    @staticmethod
    def _parse_preparer_response(raw: str) -> dict:
        """Parse LLM response, handling markdown, think blocks, extra text."""
        text = raw.strip()

        # Strip DeepSeek <think> blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # Strip markdown fences
        text = text.replace('```json', '').replace('```', '').strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract JSON from surrounding text
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Preparer: Could not parse JSON (len={len(raw)})")
