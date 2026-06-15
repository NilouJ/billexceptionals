"""
One-pass data enrichment so ground-truth labels in origin_exceptions.csv
match the underlying kraken_*.csv data. Run once; safe to re-run (idempotent).

Adds the missing flags so when an analyst clicks an "onshore" case in the
sidebar, the agents actually fire the exclusion path the gt column predicts.

Specifically:
  + Adds open Ombudsman complaints for A-10000037 and A-10000055 (triage exclude)
  + Sets isInHardship=True for A-10000005 (pre-check block via R02-03)
  + Sets hasLifeSupport=True for the user on A-10000043 (pre-check block via R02-02)
"""

import csv
from pathlib import Path

DATA = Path(__file__).parent / "data"


def _rewrite(filename: str, rows: list, fieldnames: list) -> None:
    """Write CSV with consistent newline behaviour for cross-platform git."""
    with open(DATA / filename, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _read(filename: str) -> tuple[list, list]:
    with open(DATA / filename, newline="") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def add_ombudsman(complaints: list, account_number: str, creation_date: str, comp_id: str) -> bool:
    """Add an open Ombudsman complaint if the account doesn't already have one."""
    has_open = any(
        c["account_number"] == account_number
        and c.get("isOfficial") == "True"
        and not c.get("resolutionDate")
        for c in complaints
    )
    if has_open:
        return False
    complaints.append({
        "id":             comp_id,
        "account_number": account_number,
        "type":           "OMBUDSMAN",
        "subtype":        "BILLING_DISPUTE",
        "isOfficial":     "True",
        "creationDate":   creation_date,
        "resolutionDate": "",
        "assigneeId":     "9001",
    })
    return True


def set_hardship(accounts: list, account_number: str) -> bool:
    for a in accounts:
        if a["account_number"] == account_number:
            if a["isInHardship"] == "True":
                return False
            a["isInHardship"] = "True"
            return True
    return False


def set_life_support(users: list, account_number: str) -> bool:
    changed = False
    for u in users:
        if u["account_number"] == account_number and u.get("isActive") == "True":
            if u.get("hasLifeSupport") != "True":
                u["hasLifeSupport"] = "True"
                changed = True
            break
    return changed


def main() -> int:
    complaints, comp_fields = _read("kraken_complaints.csv")
    accounts,   acct_fields = _read("kraken_accounts.csv")
    users,      user_fields = _read("kraken_account_users.csv")

    c1 = add_ombudsman(complaints, "A-10000037", "2026-04-02", "COMP-DEMO01")
    c2 = add_ombudsman(complaints, "A-10000055", "2026-04-15", "COMP-DEMO02")
    c3 = set_hardship(accounts, "A-10000005")
    c4 = set_life_support(users, "A-10000043")

    if c1 or c2:
        _rewrite("kraken_complaints.csv", complaints, comp_fields)
    if c3:
        _rewrite("kraken_accounts.csv", accounts, acct_fields)
    if c4:
        _rewrite("kraken_account_users.csv", users, user_fields)

    print(f"Ombudsman A-10000037: {'added' if c1 else 'skipped (already present)'}")
    print(f"Ombudsman A-10000055: {'added' if c2 else 'skipped (already present)'}")
    print(f"Hardship A-10000005:  {'set' if c3 else 'skipped'}")
    print(f"Life support A-10000043: {'set' if c4 else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
