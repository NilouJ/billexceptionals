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
from scenarios import classify_scenario, get_scenario
from tools import (
    get_account,
    get_metering,
    get_agreement,
    get_service_orders,
    get_pmd_requests,
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

    if account.get("isInHardship"):
        evidence["hasActiveHardship"] = True
        rule_hits.append({
            "rule_id": "R02-03",
            "reason":  "Customer flagged as in financial hardship — billing on hold pending review.",
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

    # PMD checks — proposal §2.3 GR-01 / GR-02 / GR-04
    pmd_requests = get_pmd_requests(acct_no)
    state["context"]["pmd_requests"] = pmd_requests
    evidence["pmd_request_count"] = len(pmd_requests)

    if pmd_requests:
        # GR-02 (R03-08): Rate Tariff Issue PMD takes precedence in the trace
        tariff_pmds = [p for p in pmd_requests if p.get("type") == "RATE_TARIFF_ISSUE"]
        general_pmds = [p for p in pmd_requests if p.get("type") != "RATE_TARIFF_ISSUE"]
        if tariff_pmds:
            p = tariff_pmds[0]
            rule_hits.append({
                "rule_id": "R03-08",
                "reason":  f"Active PMD raised {p.get('raised_date')} for Rate Tariff Issue — onshore tariff team owns resolution.",
            })
        if general_pmds and not tariff_pmds:
            p = general_pmds[0]
            rule_hits.append({
                "rule_id": "R03-07",
                "reason":  f"PMD request already raised on {p.get('raised_date')} (status {p.get('status')}) — case is in-flight onshore.",
            })

    # OOC threshold — proposal §2.3 GR-08
    if case.get("exception_type") == "OUT_OF_CODE":
        ooc_amount_raw = case.get("ooc_amount")
        try:
            ooc_amount = int(float(ooc_amount_raw)) if ooc_amount_raw not in (None, "", "None") else 0
        except (TypeError, ValueError):
            ooc_amount = 0
        evidence["ooc_amount"] = ooc_amount
        if ooc_amount > 5000:
            rule_hits.append({
                "rule_id": "R03-10",
                "reason":  f"OOC credit amount ${ooc_amount:,} exceeds the $5,000 threshold — onshore approval required.",
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

    # Classify scenario per FSD §3.4 (SCEN-01..09)
    scenario_code, data_available = classify_scenario(case, state["context"], state["trace"])
    scenario = get_scenario(scenario_code)
    state["context"]["scenario_code"] = scenario_code
    state["context"]["scenario"]      = scenario

    # Keep legacy `sops` list available for backward-compatible callers.
    state["context"]["sops"] = scenario["sop"]["key_steps"]

    evidence = {
        "exception_type":  exception_type,
        "scenario_code":   scenario_code,
        "scenario_title":  scenario["title"],
        "scenario_trigger": scenario["trigger"],
        "sop_id":          scenario["sop"]["id"],
        "sop_title":       scenario["sop"]["title"],
        "data_available":  data_available,
        "product_code":    agreement.get("product_code"),
        "rate_per_kwh":    agreement.get("rate_per_kwh"),
        "tdsp":            metering.get("tdsp"),
        "load_zone":       metering.get("load_zone"),
        "sops_retrieved":  len(scenario["sop"]["key_steps"]),
    }

    if scenario["sop"]["key_steps"]:
        confidence_note = "" if data_available else " (type-default — signal data not in this prototype)"
        _trace(
            state,
            "sop_context",
            "CONTEXT_ASSEMBLED",
            reasons=[f"Classified as {scenario_code}: {scenario['title']}{confidence_note}. SOP {scenario['sop']['id']} retrieved."],
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
                "reason":  f"No SOP defined for scenario {scenario_code} — flagging for human review.",
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
        scenario  = context.get("scenario", {})
        all_reasons = [
            f"Account is on supply with active {agreement.get('product_code')} agreement.",
            f"Meter reads are complete and quality is good.",
            f"Classified as {context.get('scenario_code', '—')}: {scenario.get('title', '')}.",
        ]
        summary = f"Case {case_id} is workable — allocate to billing team for processing per SOP {scenario.get('sop', {}).get('id', '—')}."

    state["result"] = {
        "recommendation": recommendation,
        "reason_codes":   all_reasons,
        "summary":        summary,
        "case_pack":      assemble_case_pack(state, recommendation, summary),
    }

    _trace(
        state,
        "screening_outcome",
        recommendation,
        reasons=[summary],
        evidence={"final_recommendation": recommendation},
    )

    return state


# ── Case-pack assembler (FSD §3.4) ─────────────────────────────────────────────

def assemble_case_pack(state: dict, recommendation: str, summary: str) -> dict:
    """
    Assemble the case-pack JSON delivered to downstream consumers (billing
    team UI, audit log, the chat agent). Pulled deterministically from state
    — no LLM in this path so the structure is guaranteed.

    Shape mirrors the proposal's `output/uc1-triage/01-functional-solution-design.md §3.4`
    case-pack contract: caseId, exceptionType, scenario, accountSummary,
    issuesIdentified, sopReference, recommendedActions, groundRuleOutputs,
    auditTrail.
    """
    case      = state["case"]
    context   = state["context"]
    trace     = state["trace"]
    account   = context.get("account", {}) or {}
    agreement = context.get("agreement", {}) or {}
    metering  = context.get("metering", {}) or {}
    scenario_code = context.get("scenario_code") or ""
    scenario      = context.get("scenario") or {}

    # accountSummary — the analyst-facing snapshot of the customer
    account_summary = {
        "account_number":     case.get("account_number"),
        "billing_name":       account.get("billingName"),
        "status":             account.get("status"),
        "is_on_supply":       account.get("isOnSupply"),
        "in_hardship":        account.get("isInHardship"),
        "meter_point_status": account.get("meterPointStatus"),
        "balance":            account.get("balance"),
        "overdue_balance":    account.get("overdueBalance"),
        "agreement_status":   agreement.get("agreement_status") or ("active" if agreement.get("product_code") else None),
        "product_code":       agreement.get("product_code"),
        "rate_per_kwh":       agreement.get("rate_per_kwh"),
        "billing_period_start": case.get("billing_period_start"),
        "billing_period_end":   case.get("billing_period_end"),
        "nmi_or_esiid":       case.get("esiid"),
        "meter_type":         metering.get("meter_type"),
        "last_read_date":     metering.get("last_read_date"),
    }

    # issuesIdentified — flatten all rule_hits across the trace
    issues = []
    for t in trace:
        for h in (t.get("rule_hits") or []):
            issues.append({
                "stage":    t.get("agent_key"),
                "rule_id":  h.get("rule_id"),
                "reason":   h.get("reason"),
            })

    # groundRuleOutputs — compact view of each agent's decision
    ground_rule_outputs = [
        {
            "agent":     t.get("agent_key"),
            "decision":  t.get("decision"),
            "rule_ids":  [h.get("rule_id") for h in (t.get("rule_hits") or [])],
        }
        for t in trace
    ]

    # auditTrail — for the production team, this becomes the Delta Lake row
    audit_trail = {
        "case_id":         case.get("case_id"),
        "screening_agents": len(trace),
        "rule_hit_count":  len(issues),
        "scenario_code":   scenario_code,
        "recommendation":  recommendation,
        "billing_period":  f"{case.get('billing_period_start','')} to {case.get('billing_period_end','')}",
    }

    return {
        "case_id":         case.get("case_id"),
        "exception_type":  case.get("exception_type"),
        "scenario":        scenario_code,
        "scenario_title":  scenario.get("title", ""),
        "account_summary": account_summary,
        "issues_identified": issues,
        "sop_reference":   scenario.get("sop", {}),
        "recommended_actions": scenario.get("recommended_actions", []),
        "ground_rule_outputs": ground_rule_outputs,
        "audit_trail":     audit_trail,
        "summary":         summary,
        "recommendation":  recommendation,
    }