"""Quick integration test for the Triangulator."""
import sys
sys.path.insert(0, '.')

from engine.triangulator import Triangulator

# Test 1: Consistent data
data_clean = {
    "total_borrowings": 5000000000,
    "cash_and_equivalents": 2000000000,
    "net_debt": 3000000000,
    "historical_revenues": [20000000000, 22000000000, 25000000000],
    "historical_ebitda_margins": [0.12, 0.13, 0.14],
    "shares_outstanding": 500000000,
    "debt_to_equity": 0.5,
}

r = Triangulator.run_all_checks(data_clean)
print(f"Test 1 (clean data): {r['overall_verdict'].upper()}")
print(f"  Passed: {r['passed']}/{r['total_checks']}")
for c in r['results']:
    status = 'PASS' if c['passed'] else 'FAIL'
    print(f"  {status} | {c['identity']}")

# Test 2: Inconsistent net debt
data_bad = dict(data_clean)
data_bad["net_debt"] = 10000000000

r2 = Triangulator.run_all_checks(data_bad)
print(f"\nTest 2 (bad net debt): {r2['overall_verdict'].upper()}")
for c in r2['results']:
    status = 'PASS' if c['passed'] else 'FAIL'
    print(f"  {status} | {c['identity']} | dev={c['deviation_pct']:.1f}%%")

print("\nAll tests completed.")
