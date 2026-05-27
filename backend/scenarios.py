"""
scenarios.py — billing scenario classification per FSD §3.4.

Each workable case is classified into one of nine scenario codes (SCEN-01 ..
SCEN-09) based on exception type and context flags collected by upstream agents.
Each scenario maps to a specific SOP reference and recommended actions.

The classification logic is deterministic — same case in, same scenario out.
Where the prototype doesn't yet have the underlying data (e.g. UHC flag,
pre-migration period), the classifier falls back to the type-default scenario
and the SCEN code's evidence flag indicates `data_available: False`.
"""

from __future__ import annotations


# ── Scenario catalogue — mirrors FSD §3.4 ────────────────────────────────────

SCENARIOS: dict[str, dict] = {
    "SCEN-01": {
        "title":   "Missing Reads — Basic Meter",
        "trigger": "Unbilled + read gap in MDH",
        "sop": {
            "id":        "SOP-BILL-042",
            "title":     "Missing Reads — Basic Meter Correction",
            "url":       "https://panviva.origin.com.au/SOP-BILL-042",
            "key_steps": [
                "Validate accumulation reads against properties readings",
                "Compare accumulation vs properties reads for misalignment",
                "Correct missing reads in Kraken",
                "Cancel any held bills and rebill the period",
            ],
        },
        "recommended_actions": [
            "Run read comparison tool (Macro)",
            "Correct reads in Kraken",
            "Cancel and rebill",
            "Check for UHC flag post-rebill",
        ],
    },
    "SCEN-02": {
        "title":   "Negative Consumption — Correction",
        "trigger": "Unbilled + negative consumption detected",
        "sop": {
            "id":        "SOP-BILL-051",
            "title":     "Negative Consumption — Correction Procedure",
            "url":       "https://panviva.origin.com.au/SOP-BILL-051",
            "key_steps": [
                "Identify the source of negative reads",
                "Validate meter polarity and configuration",
                "Apply correction and recompute usage for the period",
            ],
        },
        "recommended_actions": [
            "Review daily readings for the period",
            "Validate with field team if polarity suspected",
            "Apply correction in Kraken and rebill",
        ],
    },
    "SCEN-03": {
        "title":   "Interval Meter — PMD Initiation",
        "trigger": "Unbilled + interval meter + no PMD",
        "sop": {
            "id":        "SOP-BILL-018",
            "title":     "Interval Meter — PMD Initiation",
            "url":       "https://panviva.origin.com.au/SOP-BILL-018",
            "key_steps": [
                "Confirm interval meter type and MRIM status",
                "Raise PMD request to MDH for the period",
                "Hold the bill until PMD response received",
            ],
        },
        "recommended_actions": [
            "Raise PMD via MDH",
            "Pause billing on the account",
            "Notify customer of read estimation delay",
        ],
    },
    "SCEN-04": {
        "title":   "Unusually High Charges — Investigation",
        "trigger": "Held + UHC (Unusually High Charges) flag",
        "sop": {
            "id":        "SOP-BILL-061",
            "title":     "Unusually High Charges — Investigation",
            "url":       "https://panviva.origin.com.au/SOP-BILL-061",
            "key_steps": [
                "Compare current usage to prior periods (12-month average)",
                "Validate reads and meter accuracy",
                "Contact customer if confirmed UHC",
            ],
        },
        "recommended_actions": [
            "Run UHC comparison",
            "Validate meter reads with field team if required",
            "Initiate customer contact",
        ],
    },
    "SCEN-05": {
        "title":   "Out of Code — Checklist & Credit",
        "trigger": "Held + OOC checklist required",
        "sop": {
            "id":        "SOP-BILL-077",
            "title":     "Out of Code Checklist & Credit Calculation",
            "url":       "https://panviva.origin.com.au/SOP-BILL-077",
            "key_steps": [
                "Complete OOC checklist",
                "Calculate credit amount per current tariff",
                "Apply credit and release the held bill",
            ],
        },
        "recommended_actions": [
            "Complete OOC checklist in Kraken",
            "Calculate credit",
            "Release held bill",
        ],
    },
    "SCEN-06": {
        "title":   "Pre-Migration Billing — Legacy Correction",
        "trigger": "Reminders + pre-migration period",
        "sop": {
            "id":        "SOP-BILL-082",
            "title":     "Pre-Migration Billing — Legacy Correction",
            "url":       "https://panviva.origin.com.au/SOP-BILL-082",
            "key_steps": [
                "Identify the pre-migration billing period",
                "Use legacy correction macro",
                "Reconcile against migrated balances",
            ],
        },
        "recommended_actions": [
            "Apply legacy correction macro",
            "Reconcile balances",
            "Notify finance reconciliation team",
        ],
    },
    "SCEN-07": {
        "title":   "Final Bill Reminder — Read Alignment",
        "trigger": "Reminders + read gap (final bill)",
        "sop": {
            "id":        "SOP-BILL-088",
            "title":     "Final Bill Reminder — Read Alignment",
            "url":       "https://panviva.origin.com.au/SOP-BILL-088",
            "key_steps": [
                "Confirm final read date",
                "Align reads against move-out request",
                "Reissue final bill",
            ],
        },
        "recommended_actions": [
            "Confirm final read date in MDH",
            "Align and reissue final bill",
            "Close reminder loop",
        ],
    },
    "SCEN-08": {
        "title":   "OOC — Standard Credit Calculation",
        "trigger": "OUT_OF_CODE + amount < $5k + no QLD EM meter",
        "sop": {
            "id":        "SOP-BILL-095",
            "title":     "Out of Code — Standard Credit Calculation",
            "url":       "https://panviva.origin.com.au/SOP-BILL-095",
            "key_steps": [
                "Validate OOC amount under $5,000 offshore threshold",
                "Apply standard credit calculation",
                "Issue corrected bill",
            ],
        },
        "recommended_actions": [
            "Apply standard credit",
            "Issue corrected bill",
            "Close OOC case",
        ],
    },
    "SCEN-09": {
        "title":   "Complex Case — Senior Agent / Onshore",
        "trigger": "Any + multiple ground-rule flags",
        "sop": {
            "id":        "SOP-BILL-099",
            "title":     "Complex Case — Senior Agent Handling",
            "url":       "https://panviva.origin.com.au/SOP-BILL-099",
            "key_steps": [
                "Senior agent review of all triggered flags",
                "Coordinate with onshore for resolution",
                "Document outcome for SOP feedback loop",
            ],
        },
        "recommended_actions": [
            "Escalate to senior agent",
            "Coordinate onshore handover",
            "Document complex case for SOP refinement",
        ],
    },
}


def classify_scenario(case: dict, context: dict, trace: list | None = None) -> tuple[str, bool]:
    """
    Classify the case into one of SCEN-01..09 based on exception type +
    upstream context. Returns (scenario_code, data_available).

    data_available is False when the classification falls back to a
    type-default because the underlying signal (e.g. UHC flag) isn't yet
    surfaced by tools.py — the scenario is the *most likely* match, not
    confirmed by data.
    """
    exception_type = case.get("exception_type", "")
    metering       = context.get("metering", {}) or {}
    pmd_requests   = context.get("pmd_requests", []) or []
    meter_type     = (metering.get("meter_type") or "").upper()

    missing_pct          = float(metering.get("missing_pct", 0) or 0)
    has_read_gap         = missing_pct > 10
    is_interval_meter    = "INTERVAL" in meter_type
    has_pmd              = bool(pmd_requests)

    # Count distinct rule families that fired upstream (R01-xx, R02-xx, R03-xx)
    trace_rule_families: set[str] = set()
    for t in (trace or []):
        for h in t.get("rule_hits", []):
            fam = h.get("rule_id", "").split("-")[0] if h.get("rule_id") else ""
            if fam:
                trace_rule_families.add(fam)

    # SCEN-09 — complex case if multiple agent families flagged something
    if len(trace_rule_families) >= 2:
        return "SCEN-09", True

    if exception_type == "UNBILLED":
        if is_interval_meter and not has_pmd:
            return "SCEN-03", True
        if has_read_gap:
            return "SCEN-01", True
        return "SCEN-02", False  # negative consumption — fallback (no data signal)

    if exception_type in ("REMINDER_HELD", "HELD"):
        if has_read_gap:
            return "SCEN-07", True
        # UHC vs OOC checklist vs pre-migration — no data signal in prototype
        return "SCEN-04", False

    if exception_type == "OUT_OF_CODE":
        try:
            ooc_amount = int(float(case.get("ooc_amount") or 0))
        except (TypeError, ValueError):
            ooc_amount = 0
        # > $5k cases are caught by R03-10 at ground-rule before this runs,
        # so anything reaching here is under threshold → SCEN-08.
        if ooc_amount and ooc_amount <= 5000:
            return "SCEN-08", True
        return "SCEN-05", False

    if exception_type in ("ZERO_CONSUMPTION", "MISSING_METER_READ", "TARIFF_MISMATCH"):
        # Map onto the closest type-default scenario
        if has_read_gap:
            return "SCEN-01", True
        return "SCEN-03", False if not is_interval_meter else True

    return "SCEN-09", False  # unknown — treat as complex


def get_scenario(scenario_code: str) -> dict:
    """Return the scenario definition dict for the given code."""
    return SCENARIOS.get(scenario_code, {
        "title": "Unknown scenario",
        "trigger": "no match",
        "sop": {"id": "", "title": "", "url": "", "key_steps": []},
        "recommended_actions": [],
    })
