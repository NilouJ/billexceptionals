# 03 — Rules and Scenarios

This doc maps **what the prototype has today** (the `R01-xx`, `R02-xx`, `R03-xx`, `R04-xx` rule IDs in `backend/agents.py`) against **what the proposal designed** (`PC-01..03`, `GR-01..09`, `SCEN-01..09` in `output/uc1-triage/01-functional-solution-design.md §2.3` and §3.4 of the proposal repo).

The gaps in this table are the Day 1 work items in [`HACKATHON.md`](../HACKATHON.md).

---

## Pre-check rules (proposal §2.3) → prototype mapping

| Proposal rule | Description | Prototype rule | Status | Notes |
|---|---|---|---|---|
| **PC-01** | Active Ombudsman complaint on account | `R01-05` (in `case_intake_triage_agent`) | ✅ Done | Note: the prototype puts it in *triage* not *pre-check* — minor naming difference, behaviour identical |
| **PC-02** | Pinned "do not bill" note | `R01-06` (in `case_intake_triage_agent`) | ✅ Done | Same as above |
| **PC-03** | Temp Held Reason flag → exclude at triage | — | ❌ Missing | Day 1 candidate (low priority — Tableau extract is mock so flag would also be mocked) |

## Ground-rule check rules (proposal §2.3) → prototype mapping

| Proposal rule | Exception type | Description | Prototype rule | Status | Day 1 action |
|---|---|---|---|---|---|
| **GR-01** | Unbilled | PMD request already raised | — | ❌ Missing | **T1** — add PMD source data + rule |
| **GR-02** | Unbilled | PMD request for Rate Tariff Issue | — | ❌ Missing | **T1** — add PMD `type` field + rule |
| **GR-03** | Unbilled | Onshore clarification — not covered in SOPs | `R04-01` (in `sop_context_agent`) | ⚠️ Partial | Currently `SOP_GAP` triggers `RETURN_TO_ONSHORE_NEEDS_SOP`. Maps cleanly. |
| **GR-04** | Held / Reminders | PMD request already raised | — | ❌ Missing | **T1** — same PMD data path as GR-01 |
| **GR-05** | Held / Reminders | Missing / no meter readings (Final Bill Reminders) | `R02-06` (in `precheck_agent`) | ⚠️ Partial | Prototype checks "high missing reads >50%", not "no reads at all" for Final Bill specifically |
| **GR-06** | Held / Reminders | Onshore clarification — not covered in SOPs | `R04-01` | ⚠️ Partial | Same SOP_GAP path as GR-03 |
| **GR-07** | OOC | QLD EM meter — meter reset issue | — | ❌ Missing | **T1** — needs `meter.state` + `meter.type` check |
| **GR-08** | OOC | OOC amount > $5,000 (requires onshore approval) | — | ❌ Missing | **T1** — needs `ooc_amount` column on `origin_exceptions.csv` |
| **GR-09** | OOC | Onshore clarification — not covered in SOPs | `R04-01` | ⚠️ Partial | Same path as GR-03/06 |

## Prototype rules not in the proposal catalogue

The prototype has additional rules that go beyond the proposal's documented catalogue — useful for the demo, kept here for clarity:

| Prototype rule | Description | Source |
|---|---|---|
| `R01-01` | Account status SUSPENDED or CANCELLED | Inferred from billing common sense |
| `R01-02` | Account not on supply | `accounts.isOnSupply` flag |
| `R01-03` | Shell account | `accounts.isShellAccount` flag |
| `R01-04` | Meter point status OFF_SUPPLY | `accounts.meterPointStatus` |
| `R02-01` | Customer is deceased | `account_users.isDeceased` |
| `R02-02` | Life support equipment registered | `account_users.hasLifeSupport` |
| `R02-03` | Active hardship agreement | `accounts.isInHardship` + `activeHardshipAgreements` |
| `R02-04` | Active assistance agreement | `assistanceAgreements` |
| `R02-05` | Comm failure — 5+ consecutive zero-usage days | Derived from `daily_readings` |
| `R03-01` | No tariff agreement found | `kraken_agreements.csv` lookup |
| `R03-02` | Agreement starts after billing period | `validFrom > billing_period_start` |
| `R03-03` | Agreement expired before billing period | `validTo < billing_period_start` OR `terminatedAt < billing_period_end` |
| `R03-04` | Meter status not ACTIVE | `meter_points.status` |
| `R03-05` | Active MOVE_OUT lifecycle process | `lifecycle_processes.status` |
| `R03-06` | Other active lifecycle process | `lifecycle_processes.status` |
| `R04-01` | No SOPs found for exception type | `tools.get_sop()` returns empty |

---

## Scenario classification (proposal §3.4) → prototype gap

The proposal defines **nine billing scenarios** that the Context+SOP Agent should identify, each mapping to a specific SOP category. The prototype currently does **none** of this scenario classification — it just maps `exception_type → list of SOP strings`.

| Scenario code | Trigger conditions (per proposal §3.4) | SOP category | Prototype status |
|---|---|---|---|
| **SCEN-01** | Unbilled + read gap in MDH | Missing Reads — Basic Meters | ❌ |
| **SCEN-02** | Unbilled + negative consumption detected | Negative Consumption — Correction | ❌ |
| **SCEN-03** | Unbilled + interval meter + no PMD | Interval Meter — PMD Initiation | ❌ |
| **SCEN-04** | Held + UHC (unusually high charges) flag in Kraken | Unusually High Charges — Investigation | ❌ |
| **SCEN-05** | Held + OOC checklist required | Out of Code — Checklist & Credit | ❌ |
| **SCEN-06** | Reminders + pre-migration period | Pre-Migration Billing — Legacy Correction | ❌ |
| **SCEN-07** | Reminders + read gap (final bill) | Final Bill Reminder — Read Alignment | ❌ |
| **SCEN-08** | OOC + amount < $5k + no QLD EM | OOC — Standard Credit Calculation | ❌ |
| **SCEN-09** | Any + multiple flags (complex) | Complex Case — Senior Agent / Onshore | ❌ |

**T2 (Thursday)** refactors `sop_context_agent` to emit a `scenario_code` field per the above logic. This unlocks:

1. Richer SOP retrieval (per-scenario SOPs vs. exception-type-wide)
2. Better outcome rationale ("This is SCEN-04 — UHC Investigation")
3. Allocation hints downstream (each scenario has a complexity rating in the proposal)

---

## Case-pack output structure (proposal §3.4)

The proposal defines the JSON delivered to the billing team member after screening:

```json
{
  "caseId":         "UNB-2026-00123",
  "exceptionType":  "Unbilled",
  "scenario":       "SCEN-01",
  "accountSummary": {
    "nmi":               "...",
    "customerType":      "Residential",
    "agreementStatus":   "Active",
    "lastBillDate":      "2025-10-01",
    "outstandingPeriod": "184 days"
  },
  "issuesIdentified": [
    "Read gap detected: MDH missing reads 2025-10-01 to 2026-01-15",
    "Accumulation vs properties reads misalignment detected"
  ],
  "sopReference": {
    "id":       "SOP-BILL-042",
    "title":    "Missing Reads — Basic Meter Correction",
    "url":      "https://panviva.origin.com.au/SOP-BILL-042",
    "keySteps": ["Validate accumulation reads", "Compare vs properties reads", "Correct and rebill"]
  },
  "recommendedActions": [
    "Run read comparison tool (Macro)",
    "Correct reads in Kraken",
    "Cancel and rebill",
    "Check for UHC flag post-rebill"
  ],
  "groundRuleOutputs": { /* full ground-rule trace */ },
  "auditTrail":        { /* timestamps, agent versions, decisions */ }
}
```

The prototype's current `state["result"]` is flatter:

```python
{
    "recommendation": "WORKABLE",
    "reason_codes":   [...],
    "rationale":      "...",
    "next_action":    "...",
    "summary":        "..."
}
```

**T3 (Thursday)** restructures the result to match the case-pack contract — pulls account summary from `state["context"]["account"]`, ground-rule outputs from `state["trace"]`, etc. Most of the data already exists; this is a shape change, not new computation.

---

## HITL touchpoints (proposal §3.5) → prototype gap

The proposal defines five Team Leader touchpoints:

| ID | Trigger | Content | TL action | SLA |
|---|---|---|---|---|
| **TL-01** | Daily screening complete | Summary: total processed, excluded by reason, workable, PMD-required | Acknowledge receipt | Automatic |
| **TL-02** | Allocation approval | Case list with SOP, complexity rating, recommended agent | Approve / adjust allocation | 30 min |
| **TL-03** | Exclusion spot-check | Random sample (10%) of excluded cases | Confirm or override exclusion | 30 min |
| **TL-04** | Edge case escalation | Agent confidence < threshold | Route decision | Per SLA |
| **TL-05** | PMD queue notification | PMD-required cases | Trigger PMD to Origin Tech | Per SLA |

**T4 (Thursday)** builds a minimal version of TL-02 + TL-03 in the UI — list of cases with Approve / Override / Spot-Check buttons. No real persistence, just in-memory state — this is a demo prop, not a production HITL system.

For the demo narrative, frame this as: *"In production, this card lands in Microsoft Teams via AgentCore (per SP51) — here in the prototype, we show the equivalent screen."*
