# 04 — Demo Narrative (Origin internal judges)

**Slot:** 5 minutes live + Q&A
**Audience:** Origin internal — likely billing operations leadership, IT/architecture, maybe AI/data leadership
**Tone:** Confident, business-first, anchored to proposal numbers. Technical depth on-demand only.

The judges already know the pain (51k cases, 30 FTEs). They don't need re-educating. The demo's job is to make the future state **feel** real — the cards animating, the LLM rationale appearing, the Team Leader screen showing a green Approve button.

---

## Pre-flight checklist (T-30 min)

- [ ] Backend running on `:8000` with `LLM_PROVIDER=azure` (or `bedrock` if access has landed)
- [ ] Frontend running on `:5173`
- [ ] Browser window pre-positioned, zoomed to ~110%, dark sidebar visible
- [ ] Three demo cases pre-identified and verified:
  - [ ] **Case A** — clean WORKABLE path (all four agents PROCEED, LLM returns WORKABLE)
  - [ ] **Case B** — RETURN_TO_ONSHORE_EXCLUDED at triage (Ombudsman complaint OR pinned hold)
  - [ ] **Case C** — UNWORKABLE at ground-rule (expired agreement OR active MOVE_OUT)
- [ ] Batch endpoint working: pre-run once to warm any caches
- [ ] HITL screen pre-loaded with a few cases in "pending approval" state
- [ ] Backup screenshots taken in case anything goes wrong mid-demo
- [ ] Network is reliable (LLM call takes 3-8s; pace your narration to fill)

---

## The 5-minute flow (beat by beat)

### Beat 1 — Hook (30 seconds)

> *"Origin's billing team handles **51,370 exception cases every month**. **Thirty FTEs** spend their day doing triage, pre-checks, and ground-rule checks — work that is rule-based, repeatable, and high-confidence automatable. That's 36% of the team's capacity, and roughly $2.7M a year, gone before the team even starts working a case.*"

> *"What you're about to see is the same job, done in seconds, with a full audit trail, and with a Team Leader still in the loop."*

**Slide:** title slide (logo + one number: **30 FTEs / $2.7M**)

---

### Beat 2 — Single-case deep dive (90 seconds)

Switch to the running UI. Sidebar shows the case list. Pick **Case B** (a clear EXCLUDE).

> *"Here's a real exception case from our synthetic dataset — 100 cases that mirror Kraken's data shape. Watch the screening funnel."*

Hit **Run Screening**. The five agent cards animate left to right:

1. **Triage** — turns red, decision `RETURN_TO_ONSHORE_EXCLUDED`, badge shows `R01-05` (Ombudsman) or `R01-06` (pinned hold).
2. **Pre-check, Ground-rule, SOP Context** — SKIP. They literally don't run because the graph's conditional edges route straight to outcome.
3. **Screening Outcome** — turns green, badge shows **"Claude · Azure"** (or **Bedrock** if you've switched). Rationale appears in the right panel.

> *"Notice the three middle agents didn't fire — the graph's conditional edges short-circuited the whole funnel once Triage decided this case is out of scope. We don't waste a single tool call. And the recommendation here isn't a deterministic rule — it's Claude reading the trace and explaining in plain English why this case goes back to onshore. Full audit trail, every rule it considered, on the right."*

Click the agent card to expand the trace. Point at the `rule_hits` chips.

---

### Beat 3 — The architecture punchline (30 seconds)

> *"One thing that matters for Origin's hybrid cloud reality: this agent is **provider-agnostic**. The screening outcome agent ran just now on **Azure AI Foundry's Claude**. We can flip one env var and run the same case on **AWS Bedrock** — SP51's target platform — with zero code change."*

> *"Same model, two clouds. Origin's choice."*

**Slide (optional):** the architecture layer diagram from the proposal deck with both Bedrock and Azure AI Foundry highlighted at the model layer.

---

### Beat 4 — Batch run (60 seconds)

Switch to the batch view.

> *"Now let's run all 100 cases."*

Hit **Run Batch**. The funnel populates: how many excluded at triage, how many blocked at pre-check, how many unworkable at ground-rule, how many workable.

> *"In production, this is one daily batch of around 2,400 cases — and you can see at a glance how the funnel performs. **X% excluded** at triage, **Y% blocked** at pre-check, **Z% workable** and ready for the billing team. Scenario distribution tells you which SOPs are getting hit hardest."*

Point at the scenario chart. Read out the top two scenarios.

---

### Beat 5 — Team Leader approval (60 seconds)

Switch to the HITL view — the Team Leader screen.

> *"And critically — no bill moves without a human. Here's what the Team Leader sees: today's batch, the recommended allocations, the spot-check sample on the exclusions."*

Click **Approve** on one workable case. Watch it move to the "approved" list.

Click **Override** on an exclusion. A small dialog asks for a reason, then it routes back to the workable queue.

> *"This is **TL-02 and TL-03** from our functional design — approve allocations, spot-check exclusions. In production, this is a Microsoft Teams card via AgentCore. The principle is the same: governed autonomy. The agents run the funnel, but the human owns the decision to bill."*

---

### Beat 6 — Numbers (30 seconds)

Pull up the KPI panel.

> *"Putting numbers on it. At today's volume — 51,370 cases a month — this funnel delivers:*

> - ***30 FTEs back** into productive billing work*
> - ***Billing timeliness from 98.5% to >99%***
> - ***Turnaround time down 20 to 25%***
> - ***$2.7M annual value, just from UC-1.***

> *"That's the headline. Audit-by-design, hybrid-cloud-ready, human-in-the-loop. Happy to take questions."*

---

## Q&A — likely questions and short answers

**"How accurate is the LLM's recommendation? What if it hallucinates?"**
The recommendation is constrained to one of five enum values — anything else triggers our deterministic fallback. The rules that fire come from the four upstream deterministic agents, so the LLM is summarising, not deciding. And we've got the full rule trace shown beside every decision so the analyst can verify.

**"Why Strands and not LangGraph? Doesn't the proposal mention LangGraph?"**
SP51's architecture is "LangGraph + Strands" — they're complementary. Strands handles the agent runtime and the model abstraction; LangGraph and Strands' GraphBuilder both express the same orchestration pattern (directed graph, conditional edges). We picked Strands' GraphBuilder for the prototype because it's a tighter fit with AgentCore's runtime story — but the topology translates 1:1 to LangGraph if Origin's architecture team prefers.

**"What's the production rollout look like? Where does this code go?"**
The proposal's Production Plan (`output/uc1-triage/03-production-plan.md`) walks the full path: this prototype is the Sprint-1 spike. Production swaps CSVs for Kraken GraphQL (one file — `tools.py`), in-memory state for AgentCore Memory + DynamoDB, hard-coded SOPs for OpenSearch RAG, and the local feedback file for Delta Lake audit. The agent code does not change.

**"Did you actually train a model on Origin data?"**
No — and we wouldn't need to for this use case. The LLM is doing structured synthesis of rule outputs into a recommendation, not learning Origin-specific patterns. All the Origin-specific logic is in the deterministic rules. This is important for governance — we control the decision boundary.

**"What about PII? This is real customer data going to an LLM."**
The prototype uses synthetic data — no real customer PII. In production, the case data sent to the LLM is the **trace** (rule IDs and outcomes), not the raw customer record. We can also wire AgentCore Guardrails on the prompt path. Both architecture details are in the proposal's AI Governance Framework (`output/uc1-triage/04-ai-governance-framework.md`).

**"How long would real implementation take?"**
8 weeks for UC-1 from kickoff to pilot, per the Delivery Plan (`output/uc1-triage/02-delivery-plan.md`). The biggest dependency is Kraken API access — every other component is well-understood AWS managed services.

**"What if AWS goes down?"**
Provider abstraction. Today we showed Azure AI Foundry. The graph and rule logic are completely cloud-agnostic. We can fail over to Azure as a DR pattern, or run cross-cloud for additional resilience. Architectural choice, not a constraint.

---

## What NOT to say

- ❌ Don't apologise for the Bedrock access situation — frame it as **architecture portability**, not a workaround
- ❌ Don't go into Strands' internal API surface unless asked
- ❌ Don't say "this is just a prototype" — say "this is a working Sprint-1 spike of the SP51 architecture"
- ❌ Don't get drawn into rule-by-rule debates — point at the rule catalogue doc and offer to walk through it offline
- ❌ Don't promise specific timelines for production rollout — defer to the Delivery Plan
