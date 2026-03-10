"""
The "Checker" Agent — Financial Auditor.

Reviews the Preparer's extraction output and challenges it using
accounting standards (Ind AS / GAAP). This is the second pass in
the Maker-Checker architecture.

The Auditor does NOT see the full document — only the Preparer's
output and the specific source citations provided.
"""
from typing import Dict, Any, List
import json
import re

from engine.llm import ask_llm
from agents.prompt_builder import PromptBuilder


class AuditorAgent:
    """
    Reviews and challenges the Preparer's extraction using strict accounting logic.
    Returns per-field approval/rejection decisions.
    """

    @classmethod
    def audit(cls, system_prompt: str, preparer_output: Dict[str, Any],
              company_name: str = "") -> Dict[str, Any]:
        """
        Run the Auditor verification pass.

        Args:
            system_prompt: The auditor's system prompt
            preparer_output: Output from PreparerAgent.extract()
            company_name: Name of the target company

        Returns:
            {
                "overall_status": "approved" | "flagged" | "rejected",
                "field_verdicts": [
                    {
                        "field": "net_debt",
                        "status": "approved" | "flagged" | "rejected",
                        "auditor_confidence": 0.85,
                        "reason": "Citation verified against balance sheet..."
                    },
                    ...
                ],
                "auditor_notes": "Summary of findings...",
                "corrections": { ... any corrected values ... }
            }
        """
        extracted = preparer_output.get("extracted_data", {})
        audit_trail = preparer_output.get("audit_trail", [])
        reconciliation = preparer_output.get("reconciliation_log", "")

        # If extraction failed or is empty, skip audit
        if not extracted:
            return {
                "overall_status": "rejected",
                "field_verdicts": [],
                "auditor_notes": "No data to audit — extraction returned empty.",
                "corrections": {},
            }

        # If deterministic fallback was used, auto-approve (no LLM data to challenge)
        if preparer_output.get("extraction_mode") == "deterministic_fallback":
            verdicts = []
            for entry in audit_trail:
                verdicts.append({
                    "field": entry["field"],
                    "status": "approved",
                    "auditor_confidence": 0.6,
                    "reason": "Deterministic fallback — no citation to verify.",
                })
            return {
                "overall_status": "approved",
                "field_verdicts": verdicts,
                "auditor_notes": "Deterministic fallback used. Auto-approved with reduced confidence.",
                "corrections": {},
            }

        # Build the auditor prompt
        prompt = PromptBuilder.build_auditor_prompt(
            extracted_data=extracted,
            audit_trail=audit_trail,
            reconciliation_log=reconciliation,
            company_name=company_name,
        )

        try:
            auditor_system = PromptBuilder.get_system_prompt("auditor")
            raw_response = ask_llm(auditor_system, prompt)
            result = cls._parse_auditor_response(raw_response)
            return result

        except Exception as e:
            print(f"[Auditor] Audit failed: {e}")
            # Fail-safe: approve with reduced confidence
            verdicts = []
            for entry in audit_trail:
                verdicts.append({
                    "field": entry["field"],
                    "status": "flagged",
                    "auditor_confidence": 0.4,
                    "reason": f"Auditor unavailable ({str(e)}). Flagged for human review.",
                })
            return {
                "overall_status": "flagged",
                "field_verdicts": verdicts,
                "auditor_notes": f"Auditor agent failed: {str(e)}. All fields flagged.",
                "corrections": {},
            }

    @staticmethod
    def _parse_auditor_response(raw: str) -> dict:
        """Parse auditor LLM response."""
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

        # Fallback: return a generic flagged response
        return {
            "overall_status": "flagged",
            "field_verdicts": [],
            "auditor_notes": f"Could not parse auditor response (len={len(raw)}).",
            "corrections": {},
        }

    @classmethod
    def merge_corrections(cls, extracted_data: dict,
                          auditor_result: dict) -> dict:
        """
        Apply auditor corrections to extracted data.
        Returns a new dict with corrections merged in.
        """
        merged = dict(extracted_data)
        corrections = auditor_result.get("corrections", {})

        for field_name, corrected_value in corrections.items():
            if corrected_value is not None:
                merged[field_name] = corrected_value

        return merged
