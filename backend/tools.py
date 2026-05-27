"""
tools.py — data access layer.

Reads the 10 CSV mock datasets we generated.
Each function returns a clean dict matching what agents expect.
In production: swap CSV reads for Kraken GraphQL calls.
Agents never change — only this file changes.
"""

import csv
from pathlib import Path

DATA = Path(__file__).parent / "data"

HOLD_KEYWORDS = [
    "do not bill", "do not issue bill",
    "billing hold", "billing suspension", "pending dispute",
]


def _read(filename):
    with open(DATA / filename, newline="") as f:
        return list(csv.DictReader(f))


def get_cases_list():
    """Return all 100 exception cases for the /cases endpoint."""
    return _read("origin_exceptions.csv")


def get_account(account_number):
    """
    Return full account record including users, complaints, notes, hardship.
    Joins: accounts + account_users + complaints + account_notes.
    """
    accounts = {r["account_number"]: r for r in _read("kraken_accounts.csv")}
    acct = accounts.get(account_number, {})
    if not acct:
        return {}

    users_all = {}
    for r in _read("kraken_account_users.csv"):
        users_all.setdefault(r["account_number"], []).append(r)

    comps_all = {}
    for r in _read("kraken_complaints.csv"):
        comps_all.setdefault(r["account_number"], []).append(r)

    notes_all = {}
    for r in _read("kraken_account_notes.csv"):
        notes_all.setdefault(r["account_number"], []).append(r)

    users      = users_all.get(account_number, [])
    complaints = comps_all.get(account_number, [])
    notes      = notes_all.get(account_number, [])

    open_official = [
        c for c in complaints
        if c.get("isOfficial") == "True" and not c.get("resolutionDate")
    ]

    pinned_holds = [
        n for n in notes
        if n.get("isPinned") == "True"
        and any(kw in (n.get("body") or "").lower() for kw in HOLD_KEYWORDS)
    ]

    return {
        "account_number":           acct["account_number"],
        "status":                   acct["status"],
        "isOnSupply":               acct["isOnSupply"] == "True",
        "isShellAccount":           acct["isShellAccount"] == "True",
        "isInHardship":             acct["isInHardship"] == "True",
        "meterPointStatus":         acct["meterPointStatus"],
        "balance":                  int(float(acct.get("balance", 0))),
        "overdueBalance":           int(float(acct.get("overdueBalance", 0))),
        "billingName":              acct.get("billingName"),
        "billingEmail":             acct.get("billingEmail"),
        "users":                    users,
        "any_deceased":             any(u.get("isDeceased") == "True" for u in users),
        "any_life_support":         any(u.get("hasLifeSupport") == "True" for u in users),
        "complaints":               complaints,
        "open_official_complaints": open_official,
        "has_open_ombudsman":       len(open_official) > 0,
        "notes":                    notes,
        "pinned_hold_notes":        pinned_holds,
        "has_billing_hold":         len(pinned_holds) > 0,
        "has_active_hardship":      acct["isInHardship"] == "True",
    }


def get_metering(esiid):
    """
    Return metering data + computed comm-failure analysis.
    Joins: meter_points + daily_readings (by esiid).
    Consecutive zero algorithm: 5+ consecutive zero-usage days = comm failure.
    """
    by_esiid = {}
    for r in _read("kraken_meter_points.csv"):
        by_esiid[r["esiid"]] = r
    meter = by_esiid.get(esiid, {})

    all_readings = {}
    for r in _read("kraken_daily_readings.csv"):
        all_readings.setdefault(r["esiid"], []).append(r)

    readings = sorted(all_readings.get(esiid, []), key=lambda r: r["readAt"])

    zero_streak = max_zero = estimated_count = missing_count = 0
    for r in readings:
        usage = float(r.get("dailyUsage", 0) or 0)
        if usage == 0.0:
            zero_streak += 1
            max_zero = max(max_zero, zero_streak)
        else:
            zero_streak = 0
        if r.get("source") == "ESTIMATED":
            estimated_count += 1
        if r.get("source") == "MISSING":
            missing_count += 1

    total   = len(readings)
    est_pct     = round(estimated_count / total * 100, 1) if total else 0.0
    missing_pct = round(missing_count    / total * 100, 1) if total else 0.0

    return {
        "esiid":                 esiid,
        "meter_type":            meter.get("meterType"),
        "meter_status":          meter.get("status"),
        "tdsp":                  meter.get("tdsp") or meter.get("serviceProvider"),
        "load_zone":             meter.get("loadZone"),
        "total_reads":           total,
        "last_read_date":        readings[-1]["readAt"] if readings else None,
        "consecutive_zero_days": max_zero,
        "comm_failure_detected": max_zero >= 5,
        "estimated_pct":         est_pct,
        "missing_pct":           missing_pct,
        "high_estimated_reads":  est_pct > 50,
        "readings_sample":       readings[-5:],
    }


def get_agreement(account_number):
    """
    Return the tariff agreement for an account.
    Agents check validFrom, validTo, terminatedAt for billing period coverage.
    """
    agreements = {r["account_number"]: r for r in _read("kraken_agreements.csv")}
    ag = agreements.get(account_number, {})
    if not ag:
        return {}
    return {
        "id":                   ag.get("id"),
        "product_code":         ag.get("product_code"),
        "product_display_name": ag.get("product_displayName"),
        "rate_per_kwh":         ag.get("totalApplicableRate"),
        "valid_from":           ag.get("validFrom"),
        "valid_to":             ag.get("validTo"),
        "terminated_at":        ag.get("terminatedAt") or None,
        "is_eligible_renewal":  ag.get("isEligibleForRenewal") == "True",
        "prepay":               ag.get("product_prepay") == "True",
        "term_months":          ag.get("product_term"),
    }


def get_service_orders(account_number):
    """
    Return active lifecycle processes (move-out, leave supplier).
    Empty list = no active processes = no exclusion at ground-rule.
    """
    all_lc = {}
    for r in _read("kraken_lifecycle_processes.csv"):
        all_lc.setdefault(r["account_number"], []).append(r)

    return [
        {
            "process_id":     p.get("process_id"),
            "process_type":   p.get("process_type"),
            "status":         p.get("status"),
            "stage":          p.get("stage"),
            "requested_date": p.get("requested_date"),
        }
        for p in all_lc.get(account_number, [])
        if p.get("status") in ("PENDING", "IN_PROGRESS")
    ]


def get_pmd_requests(account_number):
    """
    Return active PMD (Provide Meter Data) requests for the account.
    Drives R03-07 (PMD already raised) and R03-08 (PMD for Rate Tariff Issue)
    — see proposal §2.3 GR-01 / GR-02 / GR-04.
    """
    try:
        rows = _read("kraken_pmd_requests.csv")
    except FileNotFoundError:
        return []
    return [
        {
            "pmd_id":      p.get("pmd_id"),
            "type":        p.get("type"),
            "status":      p.get("status"),
            "raised_date": p.get("raised_date"),
        }
        for p in rows
        if p.get("account_number") == account_number
        and p.get("status") in ("PENDING", "IN_PROGRESS")
    ]


def get_sop(exception_type):
    """
    Return SOP rules for the exception type.
    In production: Bedrock KB RAG retrieval.
    """
    SOPS = {
        "UNBILLED": [
            "Verify agreement covers billing period before processing.",
            "Check for active complaints or billing holds before issuing.",
            "Confirm meter reads are available and quality is good.",
            "If zero consumption — check for comm failure before billing.",
        ],
        "REMINDER_HELD": [
            "Check hardship flag before progressing reminder.",
            "Verify no active assistance agreements before sending.",
            "Confirm account is on supply before escalation.",
        ],
        "OUT_OF_CODE": [
            "Validate tariff code against current agreement.",
            "Check agreement expiry — may require renewal before billing.",
            "Escalate to tariff team if product code mismatch found.",
        ],
        "ZERO_CONSUMPTION": [
            "Check consecutive zero days — 5+ indicates comm failure.",
            "Verify meter status is ACTIVE before raising estimation.",
            "Do not estimate if comm failure confirmed — escalate to field.",
        ],
        "MISSING_METER_READ": [
            "Check last successful read date.",
            "Verify meter comm status and TDSP data feed.",
            "If gap exceeds 10 days escalate to metering team.",
        ],
        "TARIFF_MISMATCH": [
            "Verify current agreement product code matches billing system.",
            "Check agreement valid dates cover the billing period.",
            "Escalate to tariff operations if mismatch cannot be auto-resolved.",
        ],
    }
    return SOPS.get(exception_type, [
        f"No specific SOP found for exception type {exception_type}.",
        "Apply general billing exception handling procedure.",
    ])
