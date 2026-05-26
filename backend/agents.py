"""
agents.py — specialist agent nodes.

Rules:
  - Agents only update state. They never touch FastAPI or WebSocket.
  - Every agent calls tools to get data, applies logic, adds one trace item.
  - Every agent returns the full state dict.

State shape:
  {
    "case":    { case_id, account_number, esiid, exception_type, ... },
    "context": { data collected from tools },
    "trace":   [ { agent_key, agent, decision, reasons, rule_hits, evidence } ],
    "result":  None | { recommendation, reason_codes, summary }
  }

Trace entry:
  - rule_hits — list of { rule_id, reason } for rules that fired
  - reasons   — flat list of human strings; auto-derived from rule_hits if not given
"""

from schemas import AGENT_LABELS
from tools import (
    get_account,
    get_metering,
    get_agreement,
    get_service_orders,
    get_sop,
)


def _trace(state, agent_key, decision, rule_hits=None, reasons=None, evidence=None):
    rule_hits = rule_hits or []
    if not reasons:
        reasons = [h["reason"] for h in rule_hits]
    state["trace"].append({
        "agent_key": agent_key,
        "agent":     AGENT_LABELS[agent_key],
        "decision":  decision,
        "reasons":   reasons,
        "rule_hits": rule_hits,
        "evidence":  evidence or {},
    })


# ── Agent 1: Case Intake & Triage ──────────────────────────────────────────────

def case_intake_triage_agent(state):
    case    = state["case"]
    acct_no = case["account_number"]

    account = get_account(acct_no)
    state["context"]["account"] = account

    rule_hits = []
    evidence  = {
        "status":           account.get("status"),
        "isOnSupply":       account.get("isOnSupply"),
        "isShellAccount":   account.get("isShellAccount"),
        "meterPointStatus": account.get("meterPointStatus"),
        "open_ombudsman":   False,
        "pinned_hold":      False,
    }

    if account.get("status") in ("SUSPENDED", "CANCELLED"):
        rule_hits.append({
            "rule_id": "R01-01",
            "reason":  f"Account status is {account['status']} — cannot bill.",
        })

    if not account.get("isOnSupply", True):
        rule_hits.append({
            "rule_id": "R01-02",
            "reason":  "Account is not on supply.",
        })

    if account.get("isShellAccount", False):
        rule_hits.append({
            "rule_id": "R01-03",
            "reason":  "Shell account — no real customer.",
        })

    if account.get("meterPointStatus") == "OFF_SUPPLY":
        rule_hits.append({
            "rule_id": "R01-04",
            "reason":  "Meter point status is OFF_SUPPLY.",
        })

    complaints    = account.get("complaints", [])
    open_official = [c for c in complaints if c.get("isOfficial") and not c.get("resolutionDate")]
    if open_official:
        evidence["open_ombudsman"] = True
        rule_hits.append({
            "rule_id": "R01-05",
            "reason":  f"Active Ombudsman complaint open since {open_official[0]['creationDate']}.",
        })

    HOLD_KEYWORDS = ["do not bill", "billing hold", "billing suspension", "pending dispute"]
    notes = account.get("notes", [])
    pinned_holds = [
        n for n in notes
        if n.get("isPinned") and any(kw in (n.get("body") or "").lower() for kw in HOLD_KEYWORDS)
    ]
    if pinned_holds:
        evidence["pinned_hold"] = True
        rule_hits.append({
            "rule_id": "R01-06",
            "reason":  f"Pinned billing hold note: '{pinned_holds[0]['body'][:60]}'.",
        })

    if rule_hits:
        _trace(state, "case_intake_triage", "RETURN_TO_ONSHORE_EXCLUDED", rule_hits=rule_hits, evidence=evidence)
        state["context"]["triage_excluded"] = True
    else:
        _trace(state, "case_intake_triage", "PROCEED", reasons=["All triage checks passed."], evidence=evidence)
        state["context"]["triage_excluded"] = False

    return state


# ── Agent 2: Pre-check ─────────────────────────────────────────────────────────

def precheck_agent(state):
    case  = state["case"]
    esiid = case["esiid"]

    account  = state["context"]["account"]
    metering = get_metering(esiid)
    state["context"]["metering"] = metering

    rule_hits = []
    evidence  = {
        "isInHardship":          account.get("isInHardship"),
        "hasLifeSupport":        False,
        "hasActiveHardship":     False,
        "consecutive_zero_days": metering.get("consecutive_zero_days", 0),
        "estimated_read_pct":    metering.get("estimated_read_pct", 0),
        "read_quality":          metering.get("read_quality"),
        "last_read_date":        metering.get("last_read_date"),
    }

    users = account.get("users", [])
    if [u for u in users if u.get("isDeceased") == "True"]:
        rule_hits.append({
            "rule_id": "R02-01",
            "reason":  "Customer is deceased — cannot proceed with billing.",
        })

    if [u for u in users if u.get("hasLifeSupport") == "True"]:
        evidence["hasLifeSupport"] = True
        rule_hits.append({
            "rule_id": "R02-02",
            "reason":  "Life support equipment registered — special handling required.",
        })

    if account.get("activeHardshipAgreements"):
        evidence["hasActiveHardship"] = True
        ha = account["activeHardshipAgreements"][0]
        rule_hits.append({
            "rule_id": "R02-03",
            "reason":  f"Active hardship agreement (ends {ha.get('endDate', 'unknown')}) — billing suspended.",
        })

    if account.get("assistanceAgreements"):
        rule_hits.append({
            "rule_id": "R02-04",
            "reason":  "Active assistance agreement — billing on hold.",
        })

    zero_days = metering.get("consecutive_zero_days", 0)
    if zero_days >= 5:
        rule_hits.append({
            "rule_id": "R02-05",
            "reason":  f"Communication failure — {zero_days} consecutive days with zero consumption.",
        })

    missing_pct = metering.get("missing_pct", 0)
    if missing_pct > 50:
        rule_hits.append({
            "rule_id": "R02-06",
            "reason":  f"High MISSING reads — {missing_pct:.0f}% of reads have no data.",
        })

    if rule_hits:
        _trace(state, "precheck", "RETURN_TO_ONSHORE_BLOCKED", rule_hits=rule_hits, evidence=evidence)
        state["context"]["precheck_blocked"] = True
    else:
        _trace(state, "precheck", "PROCEED", reasons=["All pre-check validations passed."], evidence=evidence)
        state["context"]["precheck_blocked"] = False

    return state


# ── Agent 3: Ground-rule ───────────────────────────────────────────────────────

def groundrule_agent(state):
    case    = state["case"]
    acct_no = case["account_number"]
    bp_end  = case.get("billing_period_end", "")

    agreement      = get_agreement(acct_no)
    service_orders = get_service_orders(acct_no)
    metering       = state["context"].get("metering", {})

    state["context"]["agreement"]      = agreement
    state["context"]["service_orders"] = service_orders

    rule_hits = []
    evidence  = {
        "agreement_status":     agreement.get("status"),
        "agreement_valid_to":   agreement.get("valid_to"),
        "terminated_at":        agreement.get("terminated_at"),
        "product_code":         agreement.get("product_code"),
        "meter_status":         metering.get("meter_status"),
        "active_leave_process": False,
    }

    if not agreement:
        rule_hits.append({
            "rule_id": "R03-01",
            "reason":  "No tariff agreement found for this account.",
        })
    else:
        bp_start      = case.get("billing_period_start", "")
        valid_from    = agreement.get("valid_from", "")
        valid_to      = agreement.get("valid_to", "") or ""
        terminated_at = agreement.get("terminated_at") or ""

        before_start = valid_from > bp_start if valid_from else False
        expired      = (valid_to and valid_to < bp_start) if valid_to else False
        terminated   = (terminated_at and terminated_at < bp_end) if terminated_at and bp_end else False

        if before_start:
            rule_hits.append({
                "rule_id": "R03-02",
                "reason":  f"Agreement only starts {valid_from} — does not cover billing period start {bp_start}.",
            })
        if expired:
            rule_hits.append({
                "rule_id": "R03-03",
                "reason":  f"Agreement expired {valid_to} — before billing period start {bp_start}.",
            })
        if terminated:
            rule_hits.append({
                "rule_id": "R03-03",
                "reason":  f"Agreement terminated {terminated_at} — before billing period end {bp_end}.",
            })

    if metering.get("meter_status") not in ("ACTIVE", None, ""):
        rule_hits.append({
            "rule_id": "R03-04",
            "reason":  f"Meter status is {metering.get('meter_status')} — not ACTIVE.",
        })

    active_orders = [o for o in service_orders if o.get("status") in ("PENDING", "IN_PROGRESS")]
    if active_orders:
        evidence["active_leave_process"] = True
        o   = active_orders[0]
        rid = "R03-05" if o.get("process_type") == "MOVE_OUT" else "R03-06"
        rule_hits.append({
            "rule_id": rid,
            "reason":  f"Active {o.get('process_type')} process — status {o.get('status')}.",
        })

    if rule_hits:
        _trace(state, "groundrule", "RETURN_TO_ONSHORE_UNWORKABLE", rule_hits=rule_hits, evidence=evidence)
        state["context"]["groundrule_unworkable"] = True
    else:
        _trace(state, "groundrule", "WORKABLE", reasons=["Case is workable — agreement and meter valid."], evidence=evidence)
        state["context"]["groundrule_unworkable"] = False

    return state


# ── Agent 4: SOP Context ───────────────────────────────────────────────────────

def sop_context_agent(state):
    case           = state["case"]
    exception_type = case.get("exception_type", "UNBILLED")
    agreement      = state["context"].get("agreement", {})
    metering       = state["context"].get("metering", {})

    sops = get_sop(exception_type)
    state["context"]["sops"] = sops

    evidence = {
        "exception_type": exception_type,
        "product_code":   agreement.get("product_code"),
        "rate_per_kwh":   agreement.get("rate_per_kwh"),
        "tdsp":           metering.get("tdsp"),
        "load_zone":      metering.get("load_zone"),
        "sops_retrieved": len(sops),
    }

    if sops:
        _trace(
            state,
            "sop_context",
            "CONTEXT_ASSEMBLED",
            reasons=[f"Retrieved {len(sops)} SOP rules for exception type {exception_type}."],
            evidence=evidence,
        )
    else:
        state["context"]["sop_gap"] = True
        _trace(
            state,
            "sop_context",
            "SOP_GAP",
            rule_hits=[{
                "rule_id": "R04-01",
                "reason":  f"No SOPs found for exception type {exception_type} — flagging for human review.",
            }],
            evidence=evidence,
        )

    return state


# ── Agent 5: Case Screening Outcome ────────────────────────────────────────────

def case_screening_outcome_agent(state):
    case    = state["case"]
    case_id = case["case_id"]
    context = state["context"]

    all_reasons = []
    for t in state["trace"]:
        if t["decision"] not in ("PROCEED", "SKIPPED", "CONTEXT_ASSEMBLED"):
            all_reasons.extend(t.get("reasons", []))

    if context.get("triage_excluded"):
        recommendation = "RETURN_TO_ONSHORE_EXCLUDED"
        summary = f"Case {case_id} excluded at triage — route to onshore team for manual handling."

    elif context.get("precheck_blocked"):
        recommendation = "RETURN_TO_ONSHORE_BLOCKED"
        summary = f"Case {case_id} blocked at pre-check — route to onshore for specialist review."

    elif context.get("groundrule_unworkable"):
        recommendation = "RETURN_TO_ONSHORE_UNWORKABLE"
        summary = f"Case {case_id} is unworkable — route to onshore for agreement or meter resolution."

    elif context.get("sop_gap"):
        recommendation = "RETURN_TO_ONSHORE_NEEDS_SOP"
        summary = f"Case {case_id} has no matching SOP — route to human for guidance."

    else:
        recommendation = "WORKABLE"
        agreement = context.get("agreement", {})
        sops      = context.get("sops", [])
        all_reasons = [
            f"Account is on supply with active {agreement.get('product_code')} agreement.",
            f"Meter reads are complete and quality is good.",
            f"{len(sops)} SOP rules confirm workable path for {case['exception_type']}.",
        ]
        summary = f"Case {case_id} is workable — allocate to billing team for processing."

    state["result"] = {
        "recommendation": recommendation,
        "reason_codes":   all_reasons,
        "summary":        summary,
    }

    _trace(
        state,
        "screening_outcome",
        recommendation,
        reasons=[summary],
        evidence={"final_recommendation": recommendation},
    )

    return state