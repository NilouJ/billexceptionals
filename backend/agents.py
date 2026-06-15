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


def _trace(state, agent_key, decision, rule_hits=None, reasons=None, evidence=None, checks=None):
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
        "checks":    checks or [],
    })


def _verify(checks, rule_hits, rule_id, label, failed, fail_reason=None):
    """
    Record one verification result. If `failed` is truthy, also append a rule_hit
    using `fail_reason` (or `label` if no reason is given). Keeps each check's
    pass/fail visible to the UI for the green-tick / red-cross display.
    """
    if failed:
        reason = fail_reason or label
        checks.append({"rule_id": rule_id, "label": label, "passed": False, "reason": reason})
        rule_hits.append({"rule_id": rule_id, "reason": reason})
    else:
        checks.append({"rule_id": rule_id, "label": label, "passed": True})


# ── Agent 1: Case Intake & Triage ──────────────────────────────────────────────

def case_intake_triage_agent(state):
    case    = state["case"]
    acct_no = case["account_number"]

    account = get_account(acct_no)
    state["context"]["account"] = account

    rule_hits = []
    checks    = []
    evidence  = {
        "status":           account.get("status"),
        "isOnSupply":       account.get("isOnSupply"),
        "isShellAccount":   account.get("isShellAccount"),
        "meterPointStatus": account.get("meterPointStatus"),
        "open_ombudsman":   False,
        "pinned_hold":      False,
    }

    status = account.get("status")
    _verify(
        checks, rule_hits, "R01-01",
        "Account status active",
        failed=status in ("SUSPENDED", "CANCELLED"),
        fail_reason=f"Account status is {status} — cannot bill.",
    )

    _verify(
        checks, rule_hits, "R01-02",
        "Account on supply",
        failed=not account.get("isOnSupply", True),
        fail_reason="Account is not on supply.",
    )

    _verify(
        checks, rule_hits, "R01-03",
        "Real customer account",
        failed=account.get("isShellAccount", False),
        fail_reason="Shell account — no real customer.",
    )

    _verify(
        checks, rule_hits, "R01-04",
        "Meter point on supply",
        failed=account.get("meterPointStatus") == "OFF_SUPPLY",
        fail_reason="Meter point status is OFF_SUPPLY.",
    )

    complaints    = account.get("complaints", [])
    open_official = [c for c in complaints if c.get("isOfficial") and not c.get("resolutionDate")]
    if open_official:
        evidence["open_ombudsman"] = True
    _verify(
        checks, rule_hits, "R01-05",
        "No open Ombudsman complaint",
        failed=bool(open_official),
        fail_reason=(f"Active Ombudsman complaint open since {open_official[0]['creationDate']}." if open_official else None),
    )

    HOLD_KEYWORDS = ["do not bill", "billing hold", "billing suspension", "pending dispute"]
    notes = account.get("notes", [])
    pinned_holds = [
        n for n in notes
        if n.get("isPinned") and any(kw in (n.get("body") or "").lower() for kw in HOLD_KEYWORDS)
    ]
    if pinned_holds:
        evidence["pinned_hold"] = True
    _verify(
        checks, rule_hits, "R01-06",
        "No pinned billing-hold note",
        failed=bool(pinned_holds),
        fail_reason=(f"Pinned billing hold note: '{pinned_holds[0]['body'][:60]}'." if pinned_holds else None),
    )

    if rule_hits:
        _trace(state, "case_intake_triage", "RETURN_TO_ONSHORE_EXCLUDED",
               rule_hits=rule_hits, evidence=evidence, checks=checks)
        state["context"]["triage_excluded"] = True
    else:
        _trace(state, "case_intake_triage", "PROCEED",
               reasons=["All triage checks passed."], evidence=evidence, checks=checks)
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
    checks    = []
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
    deceased_users     = [u for u in users if u.get("isDeceased") == "True"]
    life_support_users = [u for u in users if u.get("hasLifeSupport") == "True"]
    if life_support_users:
        evidence["hasLifeSupport"] = True
    if account.get("isInHardship"):
        evidence["hasActiveHardship"] = True

    _verify(
        checks, rule_hits, "R02-01",
        "Customer is alive",
        failed=bool(deceased_users),
        fail_reason="Customer is deceased — cannot proceed with billing.",
    )

    _verify(
        checks, rule_hits, "R02-02",
        "No life-support equipment flag",
        failed=bool(life_support_users),
        fail_reason="Life support equipment registered — special handling required.",
    )

    _verify(
        checks, rule_hits, "R02-03",
        "Not in financial hardship",
        failed=bool(account.get("isInHardship")),
        fail_reason="Customer flagged as in financial hardship — billing on hold pending review.",
    )

    zero_days = metering.get("consecutive_zero_days", 0)
    _verify(
        checks, rule_hits, "R02-05",
        "Consistent meter reads",
        failed=zero_days >= 5,
        fail_reason=f"Communication failure — {zero_days} consecutive days with zero consumption.",
    )

    missing_pct = metering.get("missing_pct", 0)
    _verify(
        checks, rule_hits, "R02-06",
        "Read coverage above 50%",
        failed=missing_pct > 50,
        fail_reason=f"High MISSING reads — {missing_pct:.0f}% of reads have no data.",
    )

    if rule_hits:
        _trace(state, "precheck", "RETURN_TO_ONSHORE_BLOCKED",
               rule_hits=rule_hits, evidence=evidence, checks=checks)
        state["context"]["precheck_blocked"] = True
    else:
        _trace(state, "precheck", "PROCEED",
               reasons=["All pre-check validations passed."], evidence=evidence, checks=checks)
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
    checks    = []
    evidence  = {
        "agreement_status":     agreement.get("status"),
        "agreement_valid_to":   agreement.get("valid_to"),
        "terminated_at":        agreement.get("terminated_at"),
        "product_code":         agreement.get("product_code"),
        "meter_status":         metering.get("meter_status"),
        "active_leave_process": False,
    }

    _verify(
        checks, rule_hits, "R03-01",
        "Tariff agreement exists",
        failed=not agreement,
        fail_reason="No tariff agreement found for this account.",
    )

    if agreement:
        bp_start      = case.get("billing_period_start", "")
        valid_from    = agreement.get("valid_from", "")
        valid_to      = agreement.get("valid_to", "") or ""
        terminated_at = agreement.get("terminated_at") or ""

        before_start = valid_from > bp_start if valid_from else False
        expired      = (valid_to and valid_to < bp_start) if valid_to else False
        terminated   = (terminated_at and terminated_at < bp_end) if terminated_at and bp_end else False

        _verify(
            checks, rule_hits, "R03-02",
            "Agreement covers billing period start",
            failed=before_start,
            fail_reason=f"Agreement only starts {valid_from} — does not cover billing period start {bp_start}.",
        )
        _verify(
            checks, rule_hits, "R03-03",
            "Agreement not expired before billing period",
            failed=bool(expired),
            fail_reason=f"Agreement expired {valid_to} — before billing period start {bp_start}.",
        )
        _verify(
            checks, rule_hits, "R03-03",
            "Agreement not terminated before billing period end",
            failed=bool(terminated),
            fail_reason=f"Agreement terminated {terminated_at} — before billing period end {bp_end}.",
        )

    _verify(
        checks, rule_hits, "R03-04",
        "Meter status ACTIVE",
        failed=metering.get("meter_status") not in ("ACTIVE", None, ""),
        fail_reason=f"Meter status is {metering.get('meter_status')} — not ACTIVE.",
    )

    active_orders = [o for o in service_orders if o.get("status") in ("PENDING", "IN_PROGRESS")]
    if active_orders:
        evidence["active_leave_process"] = True
    active_order = active_orders[0] if active_orders else None
    active_rule_id = "R03-05" if (active_order and active_order.get("process_type") == "MOVE_OUT") else "R03-06"
    _verify(
        checks, rule_hits, active_rule_id,
        "No active move-out / leave process",
        failed=bool(active_orders),
        fail_reason=(f"Active {active_order.get('process_type')} process — status {active_order.get('status')}."
                     if active_order else None),
    )

    # PMD checks — proposal §2.3 GR-01 / GR-02 / GR-04
    pmd_requests = get_pmd_requests(acct_no)
    state["context"]["pmd_requests"] = pmd_requests
    evidence["pmd_request_count"] = len(pmd_requests)

    tariff_pmds  = [p for p in pmd_requests if p.get("type") == "RATE_TARIFF_ISSUE"]
    general_pmds = [p for p in pmd_requests if p.get("type") != "RATE_TARIFF_ISSUE"]
    _verify(
        checks, rule_hits, "R03-08",
        "No active rate-tariff PMD",
        failed=bool(tariff_pmds),
        fail_reason=(f"Active PMD raised {tariff_pmds[0].get('raised_date')} for Rate Tariff Issue — onshore tariff team owns resolution."
                     if tariff_pmds else None),
    )
    _verify(
        checks, rule_hits, "R03-07",
        "No prior PMD already raised",
        failed=bool(general_pmds and not tariff_pmds),
        fail_reason=(f"PMD request already raised on {general_pmds[0].get('raised_date')} (status {general_pmds[0].get('status')}) — case is in-flight onshore."
                     if (general_pmds and not tariff_pmds) else None),
    )

    # OOC threshold — proposal §2.3 GR-08
    if case.get("exception_type") == "OUT_OF_CODE":
        ooc_amount_raw = case.get("ooc_amount")
        try:
            ooc_amount = int(float(ooc_amount_raw)) if ooc_amount_raw not in (None, "", "None") else 0
        except (TypeError, ValueError):
            ooc_amount = 0
        evidence["ooc_amount"] = ooc_amount
        _verify(
            checks, rule_hits, "R03-10",
            "OOC amount within $5,000 threshold",
            failed=ooc_amount > 5000,
            fail_reason=f"OOC credit amount ${ooc_amount:,} exceeds the $5,000 threshold — onshore approval required.",
        )

    if rule_hits:
        _trace(state, "groundrule", "RETURN_TO_ONSHORE_UNWORKABLE",
               rule_hits=rule_hits, evidence=evidence, checks=checks)
        state["context"]["groundrule_unworkable"] = True
    else:
        _trace(state, "groundrule", "WORKABLE",
               reasons=["Case is workable — agreement and meter valid."], evidence=evidence, checks=checks)
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

    has_sop = bool(scenario["sop"]["key_steps"])
    checks  = [
        {"rule_id": "R04-S1", "label": "Scenario classified", "passed": True},
        ({"rule_id": "R04-01", "label": "SOP available for scenario", "passed": True}
         if has_sop
         else {"rule_id": "R04-01", "label": "SOP available for scenario", "passed": False,
               "reason": f"No SOP defined for scenario {scenario_code} — flagging for human review."}),
    ]

    if has_sop:
        confidence_note = "" if data_available else " (type-default — signal data not in this prototype)"
        _trace(
            state,
            "sop_context",
            "CONTEXT_ASSEMBLED",
            reasons=[f"Classified as {scenario_code}: {scenario['title']}{confidence_note}. SOP {scenario['sop']['id']} retrieved."],
            evidence=evidence,
            checks=checks,
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
            checks=checks,
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

    # Synthesised summary checks — mirror the upstream gates so the analyst can see
    # at a glance which stages cleared. Failures here are summaries; the rule_ids
    # that fired live on the originating agent's card.
    outcome_checks = [
        {"rule_id": "S1", "label": "Triage cleared",       "passed": not context.get("triage_excluded"),
         **({"reason": "Excluded at triage."}             if context.get("triage_excluded")     else {})},
        {"rule_id": "S2", "label": "Pre-check cleared",    "passed": not context.get("precheck_blocked"),
         **({"reason": "Blocked at pre-check."}           if context.get("precheck_blocked")    else {})},
        {"rule_id": "S3", "label": "Ground-rule cleared",  "passed": not context.get("groundrule_unworkable"),
         **({"reason": "Unworkable at ground-rule."}      if context.get("groundrule_unworkable") else {})},
        {"rule_id": "S4", "label": "SOP context resolved", "passed": not context.get("sop_gap"),
         **({"reason": "No SOP for classified scenario."} if context.get("sop_gap")             else {})},
    ]

    _trace(
        state,
        "screening_outcome",
        recommendation,
        reasons=[summary],
        evidence={"final_recommendation": recommendation},
        checks=outcome_checks,
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