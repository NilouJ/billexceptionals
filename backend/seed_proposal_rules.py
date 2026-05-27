"""
Seed the synthetic data with fields needed by the proposal-aligned rules:
  - PMD requests (drives R03-07 / R03-08)
  - OOC amount on origin_exceptions (drives R03-10)

Idempotent: re-running produces no churn after first run.
"""

import csv
from pathlib import Path

DATA = Path(__file__).parent / "data"


# ── PMD requests — covers GR-01 / GR-02 / GR-04 from the proposal ────────────
PMD_FIELDS = ["pmd_id", "account_number", "type", "status", "raised_date"]
PMD_ROWS = [
    # type=GENERAL — generic PMD already raised by onshore (GR-01 / GR-04)
    {"pmd_id": "PMD-DEMO01", "account_number": "A-10000010", "type": "GENERAL",
     "status": "PENDING", "raised_date": "2026-04-08"},
    {"pmd_id": "PMD-DEMO02", "account_number": "A-10000028", "type": "GENERAL",
     "status": "PENDING", "raised_date": "2026-04-12"},
    # type=RATE_TARIFF_ISSUE — tariff review PMD (GR-02)
    {"pmd_id": "PMD-DEMO03", "account_number": "A-10000061", "type": "RATE_TARIFF_ISSUE",
     "status": "PENDING", "raised_date": "2026-04-15"},
    {"pmd_id": "PMD-DEMO04", "account_number": "A-10000080", "type": "RATE_TARIFF_ISSUE",
     "status": "PENDING", "raised_date": "2026-04-20"},
]


def seed_pmd_requests() -> bool:
    path = DATA / "kraken_pmd_requests.csv"
    if path.exists():
        existing = list(csv.DictReader(open(path, newline="")))
        if existing:
            return False
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PMD_FIELDS)
        w.writeheader()
        w.writerows(PMD_ROWS)
    return True


# ── OOC amount column — drives R03-10 (OOC > $5k requires onshore approval) ──
# Populates ALL existing rows of origin_exceptions.csv; ooc_amount is meaningful
# only for OUT_OF_CODE cases and blank for everything else.

OOC_OVERRIDES = {
    # Specific cases we want to demo as > $5k onshore-approval
    "OUT_OF_CODE": {
        # account_number -> ooc_amount
        "A-10000004": 7842,    # > $5k -- triggers R03-10
        "A-10000017": 9230,    # > $5k
        "A-10000033": 4280,    # under $5k, just within rules
        "A-10000058": 6850,    # > $5k
        "A-10000069": 3120,    # under $5k
    },
}


def _ooc_default(account_number: str) -> int:
    """Deterministic plausible OOC amount under $5k for cases not overridden."""
    last = int(account_number.split("-")[-1])
    return 800 + (last % 30) * 110  # range ~$800 - ~$3,990


def seed_ooc_amounts() -> bool:
    path = DATA / "origin_exceptions.csv"
    rows = list(csv.DictReader(open(path, newline="")))
    fieldnames = list(rows[0].keys()) if rows else []
    if "ooc_amount" in fieldnames:
        return False  # already added

    fieldnames.insert(fieldnames.index("product_code") + 1, "ooc_amount")
    overrides = OOC_OVERRIDES.get("OUT_OF_CODE", {})
    for r in rows:
        if r["exception_type"] == "OUT_OF_CODE":
            r["ooc_amount"] = str(overrides.get(r["account_number"], _ooc_default(r["account_number"])))
        else:
            r["ooc_amount"] = ""

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return True


def main() -> int:
    p = seed_pmd_requests()
    o = seed_ooc_amounts()
    print(f"PMD requests:  {'seeded' if p else 'skipped (already present)'}")
    print(f"OOC amounts:   {'seeded' if o else 'skipped (already present)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
