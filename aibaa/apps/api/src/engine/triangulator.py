"""
Deterministic Double-Entry Triangulator.

Uses fundamental accounting identities to catch LLM extraction errors
BEFORE they reach the DCF engine. No LLM involved — pure Python math.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class TriangulationResult:
    """Result of a single accounting identity check."""
    identity_name: str
    passed: bool
    expected: float
    actual: float
    deviation_pct: float
    details: str
    severity: str = "info"  # info, warning, critical


class Triangulator:
    """
    Validates extracted financial data using accounting identities.
    If numbers deviate beyond tolerance, the extraction is flagged.
    """

    TOLERANCE = 0.05  # 5% margin of error

    @classmethod
    def run_all_checks(cls, data: dict) -> Dict[str, Any]:
        """
        Run every applicable accounting identity check on extracted data.
        Returns a summary with pass/fail per check and an overall verdict.
        """
        results: List[TriangulationResult] = []

        # 1. Net Debt Identity
        r = cls.check_net_debt_identity(data)
        if r:
            results.append(r)

        # 2. EBITDA Reconciliation
        r = cls.check_ebitda_reconciliation(data)
        if r:
            results.append(r)

        # 3. Revenue-Margin Cross-Check
        r = cls.check_revenue_margin_crosscheck(data)
        if r:
            results.append(r)

        # 4. Shares Sanity
        r = cls.check_shares_sanity(data)
        if r:
            results.append(r)

        # 5. Debt-to-Equity Consistency
        r = cls.check_de_consistency(data)
        if r:
            results.append(r)

        # 6. Cash Flow Triangulation
        r = cls.check_cash_flow_triangulation(data)
        if r:
            results.append(r)

        # 7. Implied EV/EBITDA Multiple
        r = cls.check_implied_ev_ebitda(data)
        if r:
            results.append(r)

        # 8. Lease Liability Inclusion (Ind AS 116)
        r = cls.check_lease_liability_inclusion(data)
        if r:
            results.append(r)

        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        critical = [r for r in failed if r.severity == "critical"]

        overall = "pass"
        if critical:
            overall = "halt"
        elif failed:
            overall = "warning"

        return {
            "overall_verdict": overall,
            "total_checks": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "critical_failures": len(critical),
            "results": [
                {
                    "identity": r.identity_name,
                    "passed": r.passed,
                    "expected": round(r.expected, 2),
                    "actual": round(r.actual, 2),
                    "deviation_pct": round(r.deviation_pct, 2),
                    "details": r.details,
                    "severity": r.severity,
                }
                for r in results
            ],
        }

    # ------------------------------------------------------------------
    # Individual Identity Checks
    # ------------------------------------------------------------------

    @classmethod
    def check_net_debt_identity(cls, data: dict) -> Optional[TriangulationResult]:
        """Net Debt = Total Borrowings − Cash & Equivalents"""
        borrowings = data.get("total_borrowings")
        cash = data.get("cash_and_equivalents")
        net_debt = data.get("net_debt")

        if borrowings is None or cash is None or net_debt is None:
            return None

        try:
            borrowings = float(borrowings)
            cash = float(cash)
            net_debt = float(net_debt)
        except (ValueError, TypeError):
            return None

        expected = borrowings - cash
        deviation = abs(expected - net_debt) / max(abs(expected), 1)

        return TriangulationResult(
            identity_name="Net Debt = Borrowings − Cash",
            passed=deviation <= cls.TOLERANCE,
            expected=expected,
            actual=net_debt,
            deviation_pct=deviation * 100,
            details=f"Borrowings={borrowings:,.0f}, Cash={cash:,.0f}, "
                    f"Expected ND={expected:,.0f}, Reported ND={net_debt:,.0f}",
            severity="critical" if deviation > 0.20 else "warning",
        )

    @classmethod
    def check_ebitda_reconciliation(cls, data: dict) -> Optional[TriangulationResult]:
        """
        EBITDA ≈ Revenue × EBITDA Margin (for latest year).
        Validates that the margin and revenue are internally consistent.
        """
        revenues = data.get("historical_revenues")
        margins = data.get("historical_ebitda_margins")

        if not revenues or not margins:
            return None
        if not isinstance(revenues, list) or not isinstance(margins, list):
            return None
        if len(revenues) == 0 or len(margins) == 0:
            return None

        try:
            latest_rev = float(revenues[-1])
            latest_margin = float(margins[-1])
        except (ValueError, TypeError, IndexError):
            return None

        if latest_rev <= 0:
            return None

        implied_ebitda = latest_rev * latest_margin

        # If we have explicit EBITDA, compare
        explicit_ebitda = data.get("latest_ebitda")
        if explicit_ebitda is not None:
            try:
                explicit_ebitda = float(explicit_ebitda)
                deviation = abs(implied_ebitda - explicit_ebitda) / max(abs(explicit_ebitda), 1)
                return TriangulationResult(
                    identity_name="EBITDA = Revenue × Margin",
                    passed=deviation <= cls.TOLERANCE,
                    expected=implied_ebitda,
                    actual=explicit_ebitda,
                    deviation_pct=deviation * 100,
                    details=f"Rev={latest_rev:,.0f}, Margin={latest_margin:.2%}, "
                            f"Implied EBITDA={implied_ebitda:,.0f}, Reported={explicit_ebitda:,.0f}",
                    severity="warning",
                )
            except (ValueError, TypeError):
                pass

        # Basic sanity: margin should be between -100% and +80%
        margin_ok = -1.0 <= latest_margin <= 0.80
        return TriangulationResult(
            identity_name="EBITDA Margin Range Check",
            passed=margin_ok,
            expected=0.0,  # placeholder
            actual=latest_margin,
            deviation_pct=0.0 if margin_ok else abs(latest_margin) * 100,
            details=f"Margin={latest_margin:.2%}, "
                    f"{'within' if margin_ok else 'outside'} [-100%, +80%] range",
            severity="info" if margin_ok else "warning",
        )

    @classmethod
    def check_revenue_margin_crosscheck(cls, data: dict) -> Optional[TriangulationResult]:
        """Check that revenue trend and margin arrays have equal length."""
        revenues = data.get("historical_revenues", [])
        margins = data.get("historical_ebitda_margins", [])

        if not revenues or not margins:
            return None

        matched = len(revenues) == len(margins)
        return TriangulationResult(
            identity_name="Revenue-Margin Array Length Match",
            passed=matched,
            expected=float(len(revenues)),
            actual=float(len(margins)),
            deviation_pct=0.0 if matched else abs(len(revenues) - len(margins)) / max(len(revenues), 1) * 100,
            details=f"Revenues: {len(revenues)} years, Margins: {len(margins)} years",
            severity="critical" if not matched else "info",
        )

    @classmethod
    def check_shares_sanity(cls, data: dict) -> Optional[TriangulationResult]:
        """
        Shares outstanding should be between 4.2M (small-cap) and 6.4B (mega-cap).
        Also cross-check: if share capital and face value are provided.
        """
        shares = data.get("shares_outstanding")
        if shares is None:
            return None

        try:
            shares = float(shares)
        except (ValueError, TypeError):
            return None

        MIN_SHARES = 4_200_000        # 42 Lakh (smallest listed cos)
        MAX_SHARES = 6_400_000_000    # 640 Crore (TCS-class mega cap)

        in_range = MIN_SHARES <= shares <= MAX_SHARES

        return TriangulationResult(
            identity_name="Shares Outstanding Range Check",
            passed=in_range,
            expected=(MIN_SHARES + MAX_SHARES) / 2,
            actual=shares,
            deviation_pct=0.0 if in_range else 100.0,
            details=f"Shares={shares:,.0f}, "
                    f"Range=[{MIN_SHARES:,.0f}, {MAX_SHARES:,.0f}]",
            severity="critical" if not in_range else "info",
        )

    @classmethod
    def check_de_consistency(cls, data: dict) -> Optional[TriangulationResult]:
        """If borrowings=0, debt_to_equity must be 0."""
        borrowings = data.get("total_borrowings")
        de = data.get("debt_to_equity")

        if borrowings is None or de is None:
            return None

        try:
            borrowings = float(borrowings)
            de = float(de)
        except (ValueError, TypeError):
            return None

        if borrowings <= 0 and de > 0:
            return TriangulationResult(
                identity_name="D/E Consistency (Zero-Debt)",
                passed=False,
                expected=0.0,
                actual=de,
                deviation_pct=100.0,
                details=f"Borrowings={borrowings:,.0f} but D/E={de:.2f} (should be 0)",
                severity="warning",
            )

        return TriangulationResult(
            identity_name="D/E Consistency",
            passed=True,
            expected=de,
            actual=de,
            deviation_pct=0.0,
            details=f"Borrowings={borrowings:,.0f}, D/E={de:.2f} — consistent",
            severity="info",
        )

    @classmethod
    def check_cash_flow_triangulation(cls, data: dict) -> Optional[TriangulationResult]:
        """
        Net Income + D&A ± WC changes ≈ Operating Cash Flow.
        Only runs if all 3 components are available.
        """
        net_income = data.get("net_income")
        da = data.get("depreciation_amortization")
        ocf = data.get("operating_cash_flow")

        if net_income is None or da is None or ocf is None:
            return None

        try:
            net_income = float(net_income)
            da = float(da)
            ocf = float(ocf)
        except (ValueError, TypeError):
            return None

        # Simplified: NI + D&A should be within ~30% of OCF (WC changes can be large)
        implied_ocf = net_income + da
        deviation = abs(implied_ocf - ocf) / max(abs(ocf), 1)

        return TriangulationResult(
            identity_name="Cash Flow Triangulation (NI + D&A ≈ OCF)",
            passed=deviation <= 0.30,  # Wider tolerance due to WC
            expected=implied_ocf,
            actual=ocf,
            deviation_pct=deviation * 100,
            details=f"NI={net_income:,.0f} + D&A={da:,.0f} = {implied_ocf:,.0f}, "
                    f"OCF={ocf:,.0f}",
            severity="warning" if deviation > 0.30 else "info",
        )

    @classmethod
    def check_implied_ev_ebitda(cls, data: dict) -> Optional[TriangulationResult]:
        """
        Cross-check: If enterprise_value and terminal EBITDA are available,
        compute the implied EV/EBITDA multiple. Flag if it's unreasonable.
        
        Typical ranges for Indian consumer discretionary: 15-30x
        - Warning: <5x or >35x
        - Critical: <3x or >50x  
        """
        ev = data.get("enterprise_value")
        terminal_ebitda = data.get("terminal_ebitda")
        
        if ev is None or terminal_ebitda is None:
            return None
        
        try:
            ev = float(ev)
            terminal_ebitda = float(terminal_ebitda)
        except (ValueError, TypeError):
            return None
        
        if terminal_ebitda <= 0:
            return TriangulationResult(
                identity_name="Implied EV/EBITDA Multiple",
                passed=False,
                expected=20.0,
                actual=0.0,
                deviation_pct=100.0,
                details=f"Terminal EBITDA={terminal_ebitda:,.0f} is non-positive, cannot compute multiple",
                severity="critical",
            )
        
        implied_multiple = ev / terminal_ebitda
        
        # Define reasonable ranges
        if implied_multiple < 3.0 or implied_multiple > 50.0:
            severity = "critical"
            passed = False
        elif implied_multiple < 5.0 or implied_multiple > 35.0:
            severity = "warning"
            passed = False
        else:
            severity = "info"
            passed = True
        
        return TriangulationResult(
            identity_name="Implied EV/EBITDA Multiple",
            passed=passed,
            expected=20.0,  # Midpoint of reasonable range
            actual=implied_multiple,
            deviation_pct=abs(implied_multiple - 20.0) / 20.0 * 100,
            details=f"EV={ev:,.0f}, Terminal EBITDA={terminal_ebitda:,.0f}, "
                    f"Implied Multiple={implied_multiple:.1f}x "
                    f"({'reasonable' if passed else 'outside 5-35x range'})",
            severity=severity,
        )

    @classmethod
    def check_lease_liability_inclusion(cls, data: dict) -> Optional[TriangulationResult]:
        """
        If lease liabilities are present but net_debt doesn't include them,
        flag the inconsistency.
        """
        lease = data.get("lease_liabilities")
        borrowings = data.get("total_borrowings")
        cash = data.get("cash_and_equivalents")
        net_debt = data.get("net_debt")
        
        if lease is None or borrowings is None or cash is None or net_debt is None:
            return None
        
        try:
            lease = float(lease)
            borrowings = float(borrowings)
            cash = float(cash)
            net_debt = float(net_debt)
        except (ValueError, TypeError):
            return None
        
        if lease <= 0:
            return None
        
        expected_nd = borrowings + lease - cash
        deviation = abs(expected_nd - net_debt) / max(abs(expected_nd), 1)
        
        return TriangulationResult(
            identity_name="Net Debt includes Lease Liabilities (Ind AS 116)",
            passed=deviation <= cls.TOLERANCE,
            expected=expected_nd,
            actual=net_debt,
            deviation_pct=deviation * 100,
            details=f"Borrowings={borrowings:,.0f} + Leases={lease:,.0f} - Cash={cash:,.0f} "
                    f"= Expected ND={expected_nd:,.0f}, Actual ND={net_debt:,.0f}",
            severity="warning" if deviation > cls.TOLERANCE else "info",
        )

