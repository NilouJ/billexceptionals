# UC-1 Triage Hackathon — Thursday/Friday Plan

**Squad:** Origin × Accenture hackathon team
**Dates:** Thursday + Friday (this week)
**Judges:** Origin internal
**Deliverable:** Live demo + deck + working code in this repo

---

## The narrative — what we're selling

Origin Energy's billing back-office processes **51,370 exception cases per month** across Unbilled, Held/Reminders, and Out-of-Code categories. Today, **30 FTEs — 36% of the entire billing team's capacity** — are consumed by *triage, pre-checks, and ground-rule checks*: a structured, rule-driven workflow that is highly automatable.

This prototype replaces those four manual stages with a **multi-agent screening funnel** that runs the same case in seconds, with an audit trail, and produces a recommendation a Team Leader approves before any bill moves.

**Headline numbers (from the proposal):**

| Metric | Baseline | Target |
|---|---|---|
| FTE freed from screening | 0 | **30 FTEs (36% of team)** |
| Billing timeliness | 98.5% | **>99%** |
| Annual value (UC-1 alone) | — | **~$2.7M** |
| TAT reduction | — | **20–25%** |

*Source: `output/uc1-triage/01-functional-solution-design.md §1` in the proposal repo.*

The provider-agnostic LLM design (Bedrock OR Azure AI Foundry) is the deliberate architecture punchline: **same model, two clouds — Origin's choice.**

---

## What's already done (pre-hackathon, Wed)

- ✅ Real Strands multi-agent graph with 5 nodes and conditional skip edges (`backend/graph_topology.py`)
- ✅ Provider abstraction — `LLM_PROVIDER=bedrock|azure|deterministic` (`backend/model_provider.py`)
- ✅ Azure AI Foundry support via Strands AnthropicModel pointed at Foundry's `/anthropic/` endpoint
- ✅ Graceful fallback to deterministic outcome on any LLM failure — demo never breaks
- ✅ React + WebSocket UI streaming agent cards live, with provider badges (Bedrock blue / Azure purple / Fallback amber)
- ✅ 10 synthetic CSVs mocking Kraken's shape, 100 exception cases ready
- ✅ Feedback capture endpoint (`/feedback` → `data/feedback_store.json`)
- ✅ Docs structure (`docs/` + this file + README)

## What we're building — Day 1 (Thursday)

**Goal:** Close the gap between the prototype's rule coverage and the proposal's PC/GR catalogue, add the SCEN-01..09 scenario classification, and stand up the Team Leader HITL view.

### T1 — Rule catalogue extension *(backend lead, ~3h)*

Add the proposal's missing exclusion rules. Each new rule needs a `rule_id`, a `tools.py` data path, and an entry in the relevant agent.

| New rule | Source agent | Data path |
|---|---|---|
| **GR-01 / GR-04: PMD already raised** | groundrule | Add `pmd_status` column to `kraken_lifecycle_processes.csv` or new `kraken_pmd_requests.csv` |
| **GR-02: PMD for Rate Tariff Issue** | groundrule | Type field on PMD record |
| **GR-07: QLD EM meter (OOC cases)** | groundrule | `meter.state` + `meter.type` on `kraken_meter_points.csv` |
| **GR-08: OOC amount > $5,000** | groundrule | Add `ooc_amount` to `origin_exceptions.csv` |

See [`docs/03-rules-and-scenarios.md`](docs/03-rules-and-scenarios.md) for the full mapping table.

### T2 — Scenario classification (SCEN-01..09) *(backend lead, ~2h)*

Refactor `sop_context_agent` to emit a `scenario_code` per the proposal's §3.4 logic — not just an SOP-list-by-exception-type. Each scenario triggers a specific SOP category.

### T3 — Case-pack JSON output *(backend lead, ~1h)*

Restructure `state["result"]` to match the case-pack contract from `01-functional-solution-design.md §3.4`:

```json
{
  "caseId": "...", "exceptionType": "...", "scenario": "SCEN-01",
  "accountSummary": {...}, "issuesIdentified": [...],
  "sopReference": {...}, "recommendedActions": [...],
  "groundRuleOutputs": {...}, "auditTrail": {...}
}
```

### T4 — Team Leader HITL view *(frontend lead, ~4h)*

New screen in the UI: list of cases run today with Approve / Override / Spot-Check actions. This is the demo's emotional payoff — judges see a real human-in-the-loop gate, not an autonomous robot.

Wire-frame in [`docs/04-demo-narrative.md`](docs/04-demo-narrative.md).

---

## What we're building — Day 2 (Friday)

**Goal:** Batch run, KPI panel, polish, demo rehearsal x2.

### T5 — Batch endpoint `/screen/batch` *(backend lead, ~2h)*

Process all 100 cases through the graph, stream aggregate funnel: how many excluded at each stage, by reason, by scenario.

### T6 — KPI panel *(frontend lead, ~2h)*

Anchor the on-screen numbers to proposal targets:

> *"x of 100 → onshore (≈y of 51,370/mo); ≈z FTEs freed; ≈$N annualised at current AHT."*

The math is in `02-delivery-plan.md` of the proposal repo.

### T7 — SOP RAG (stretch) *(if anyone has capacity, ~3h)*

Swap `tools.py:get_sop()`'s hard-coded dict for **Bedrock Knowledge Bases** OR **Azure AI Search** — same provider-agnostic principle. Drops first if time slips.

### T8 — Deck refresh *(Rafael, ~3h)*

Pull from `output/uc1-triage/slides/Origin_UC1_Proposal_Deck_Native.pptx`. Reuse the FTE-impact slide, the architecture diagram, the swim-lane comparison. Add 3 new slides:
1. "Live demo" placeholder
2. Provider-agnostic architecture story (Bedrock + Azure AI Foundry)
3. Day-2 outcomes (KPIs from the batch run)

### T9 — Demo rehearsal *(whole squad, 2 × 30min)*

Once at lunch Friday, once 1h before judging.

---

## Cut list (if Friday gets tight)

In strict drop order:

1. **SOP RAG (T7)** — drop first, the deterministic dict already shows the SOP delivery
2. **KPI panel (T6)** — verbal narration of the numbers is fine if visual isn't ready
3. **Batch endpoint (T5)** — single-case demo + one canned screenshot of "if we ran all 100" works
4. **HITL view (T4)** — DO NOT drop. This is the killer moment.
5. **Rule extensions (T1) + Scenarios (T2)** — DO NOT drop. This is what makes the demo proposal-credible.

---

## Demo flow (5 minutes — judging slot)

See [`docs/04-demo-narrative.md`](docs/04-demo-narrative.md) for the full beat-by-beat. The shape:

1. **Hook (30s)** — "Origin spends 30 FTEs and ~$2.7M/year on what is fundamentally a rule-based workflow. Here's the same job in seconds."
2. **Single-case deep dive (90s)** — pick an EXCLUDE case, hit Run, watch the cards stream. Land on the LLM-generated rationale.
3. **Provider switch (30s)** — flip the env var, run again. *"Same model, two clouds — Origin's choice."*
4. **Batch run (60s)** — kick off all 100 cases, show the funnel + scenario distribution.
5. **HITL approval (60s)** — Team Leader screen, approve one batch, override one. *"No bill moves without a human."*
6. **Numbers (30s)** — KPI panel anchored to proposal. *"30 FTEs back. $2.7M/year. Audit by design."*

---

## Roles (placeholders — fill in once squad confirmed)

| Role | Owner | Day 1 | Day 2 |
|---|---|---|---|
| Backend / Strands | TBD | T1, T2, T3 | T5 (batch), T7 (RAG stretch) |
| Frontend / HITL | TBD | T4 (HITL view) | T6 (KPI panel) |
| Deck + narrative | Rafael | Coordination + content | T8 (deck), T9 (rehearsal) |
| Demo driver | TBD | — | T9 (rehearsal x2) |

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| AWS Bedrock access doesn't land by Thursday | **Already mitigated** — provider abstraction lets us run Azure AI Foundry end-to-end. Flip a single env var if Bedrock arrives mid-hackathon. |
| Foundry deployment misconfigured (auth or model name) | Smoke-test Wednesday evening with `LLM_PROVIDER=azure` against a single case before the team arrives. |
| Rule extensions take longer than 3h | Cut order in the cut-list above. The 4 most impactful rules (PMD, QLD meter, OOC > $5k) take priority — drop the rest. |
| HITL view rabbit-hole | Keep the UI dumb: just a list + Approve button. No real persistence, just in-memory state. Audit log is the proposal feature; here it's a demo prop. |
| LLM hallucinates outside the allowed recommendations | Already mitigated — `LLMOutcomeNode` validates against `ALLOWED_RECOMMENDATIONS` and falls back deterministic on any error. |
