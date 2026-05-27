# UC-1 Triage Hackathon — Thursday/Friday Plan

**Squad:** Origin × Accenture hackathon team
**Dates:** Thursday 2026-05-28 + Friday 2026-05-29
**Judges:** Origin internal
**Deliverable:** Live demo + deck + working code in this repo

Start here: [`docs/05-success-criteria.md`](docs/05-success-criteria.md) for the *what we're aiming for and why*. This file is the **how** — work plan, roles, cut list.

---

## Pre-hackathon (Tuesday/Wednesday) — done

Branch `hackathon-prep` already has the following landed and tested:

- ✅ Real Strands multi-agent graph with 5 nodes and conditional skip edges
- ✅ Provider abstraction — `LLM_PROVIDER=bedrock | azure | deterministic` (`backend/model_provider.py`)
- ✅ Azure AI Foundry support via Strands `AnthropicModel` against Foundry's `/anthropic/` endpoint (smoke-tested end-to-end against `claude-sonnet-4-6`)
- ✅ Deterministic fallback if the LLM call fails — demo never breaks
- ✅ Origin branding pass (W1) — palette, logo, header, light-mode UI
- ✅ Case search + filter pills in the sidebar
- ✅ Demo data enrichment (W6) — 4 accounts seeded with the flags their ground-truth labels predict; R02-03 hardship bug fixed
- ✅ Rule catalogue extension (T1) — R03-07 / R03-08 (PMD raised, Rate Tariff PMD), R03-10 (OOC > $5k threshold)
- ✅ Scenario classification (T2) — SCEN-01..09 per FSD §3.4 in `scenarios.py`
- ✅ Case-pack JSON output (T3) — `state["result"]["case_pack"]` matches FSD §3.4 contract; assembled deterministically from state
- ✅ Chat backend (W2) — `backend/chat.py` + `/ws/chat` WebSocket, streaming, per-case in-memory conversation
- ✅ Chat UI panel (W3) — right-side ChatPanel with 3 starter questions + streaming responses
- ✅ Data drill-down (W4) — agent cards expandable with rule chips and evidence dict
- ✅ Guided next-action chips (W5) — outcome-sized action buttons after FinalResult
- ✅ Smoke test scripts (`backend/smoke_test_provider.py` and `smoke_test_graph.py`) for quick verification
- ✅ Docs structure: README, HACKATHON.md, docs/01-04 (architecture, providers, rules, demo narrative), docs/05 (success criteria)

The squad arrives Thursday morning to a **working, branded, chat-enabled prototype** running locally with Azure AI Foundry.

---

## What's left — Thursday + Friday

### Day 1 — Thursday: HITL view + Bedrock validation

| ID | Task | Owner | Effort | Why |
|---|---|---|---|---|
| **T4** | **Team Leader HITL view** — new screen listing today's cases with Approve / Override / Spot-Check actions. The governance story for judges. | Frontend lead | 4h | S3 (guided), S5 (production-credible governance) |
| **W7** | **AWS Bedrock validation** — when access lands, smoke-test against `claude-sonnet-4-5`. Just flip `LLM_PROVIDER=bedrock` in `backend/.env`. If anything breaks, fix model_provider.py before noon. | Backend lead | 1h | S5 (SP51 target platform proven) |
| **T9-prep** | Pick the 3 hero demo cases (1 WORKABLE, 1 EXCLUDE_AT_TRIAGE, 1 UNWORKABLE) — rehearse asking the chat the same 3 questions on each so the demo runs predictably | Rafael | 2h | S1, S2, S3 |
| **Polish** | Inline error states, empty states, mobile-narrow handling (judge laptops can be quirky), no-screen-flash-on-reload | Frontend lead | 2h | S4, S5 |

### Day 2 — Friday: scale, deck, rehearsal

| ID | Task | Owner | Effort | Why |
|---|---|---|---|---|
| **T5** | **`/screen/batch` endpoint** — process all 100 cases, stream aggregate funnel | Backend lead | 2h | S5 (volume story) |
| **T6** | **KPI panel** — funnel chart + 3 headline numbers (FTEs freed, $M/year, TAT) anchored to proposal targets | Frontend lead | 2h | S3, S5 |
| **T7** | **SOP RAG (stretch)** — swap `scenarios.py` hardcoded SOPs for Bedrock KB or Azure AI Search. Drops first if Friday is tight. | Anyone | 3h | S1, S5 |
| **T8** | **Deck refresh** — pull base slides from `output/uc1-triage/slides/Origin_UC1_Proposal_Deck_Native.pptx`. Add: demo placeholder, "same model two clouds" architecture slide, Day-2 KPIs. | Rafael | 3h | Sales-ready |
| **T9** | **Demo rehearsal × 2** — once at lunch, once 1h before judging | Whole squad | 2h | Lands the demo |

---

## Cut list if Friday gets tight

Strict drop order — drop top-down:

1. **T7 SOP RAG** — scenarios.py already has SOPs; RAG is icing
2. **T6 KPI panel** — verbal narration ("at 51,370 cases/month, this is roughly 30 FTEs freed") works
3. **T5 Batch endpoint** — show a screenshot of the funnel instead of running live
4. **W7 Bedrock validation** — if access never arrives, Azure Foundry is the demo. *Same model, two clouds* — that's the architecture story
5. **T4 HITL view** — **last resort cut**. Chat handles part of the governance story but HITL adds the visible human gate
6. **DO NOT cut**: anything pre-hackathon already done, polish, rehearsal

---

## Demo flow (5 minutes)

Detail in [`docs/04-demo-narrative.md`](docs/04-demo-narrative.md). Shape:

1. **Hook (30s)** — *"30 FTEs, $2.7M, 51,370 cases. Watch the same job in seconds."*
2. **Case + screening (90s)** — pick a case → Run Screening → 5 cards stream → land on the recommendation
3. **Drill-down (45s)** — click an agent card → see the rules that fired + evidence. Click another → see scenario classification → see the SOP reference and recommended actions.
4. **Chat (75s)** — *"Why was this excluded?"* → Claude streams a plain-English answer citing rule IDs. Follow up: *"Show me the meter reads."* → Claude pulls from the case state.
5. **Next action (15s)** — click "Send to onshore queue" — case routes. Click "Ask the assistant" — chat focuses for the analyst.
6. **Architecture punchline (30s)** — *"Provider-agnostic. Today on Azure AI Foundry. Flip an env var, runs on Bedrock — SP51's target. Same model, two clouds — Origin's choice."*
7. **Numbers + close (30s)** — KPI panel (if T6 lands) — *30 FTEs / $2.7M / >99% timeliness / 13-week build path.*

---

## Roles

| Track | Day 1 (Thu) | Day 2 (Fri) |
|---|---|---|
| **Backend lead** | T4-backend support, W7 Bedrock validation | T5 batch endpoint, T7 RAG stretch |
| **Frontend lead** | T4 HITL view, polish | T6 KPI panel, integration polish |
| **Coordinator** (Rafael) | T9-prep hero cases, standups | T8 deck, T9 rehearsal × 2 |
| **Demo driver** | TBD | T9 rehearsal x2 |

---

## Risks

| Risk | Mitigation |
|---|---|
| AWS Bedrock access doesn't land by Thursday | Already mitigated — Azure AI Foundry is the demo path. Bedrock validation is a Thursday-morning *bonus*, not a blocker. |
| LLM call fails mid-demo (network, throttle) | Already mitigated — `LLMOutcomeNode` falls back to deterministic outcome and shows FALLBACK badge. Demo continues. |
| Chat hallucinates outside the case data | Already mitigated — system prompt is strict: *"If unsure, say 'I don't have that data in this case' — never fabricate."* |
| Wrong case picked on stage that doesn't trip the expected rule | Already mitigated — W6 enrichment + the T9-prep hero-case rehearsal locks in 3 predictable cases. |
| T4 HITL rabbit-hole (backend persistence, real approval queue) | Keep it dumb — in-memory list, Approve/Override buttons that just update local state. Audit log is a demo prop, not a real Delta Lake row. |
| Two devs collide on App.css | Set up branches per feature; PR small. Or coordinate via Slack. |

---

## Repo + branch workflow

| | |
|---|---|
| Main branch | `master` (protected — squad doesn't push here) |
| Working branch | `hackathon-prep` (this branch, where the pre-hackathon work lives) |
| Squad branches | Per-feature off `hackathon-prep` (e.g. `hitl-view`, `kpi-panel`) — merge back via PR |
| Friday afternoon | Final merge `hackathon-prep` → `master` after rehearsal pass |
| Demo machine | Pull `hackathon-prep` (or master after Friday merge); `LLM_PROVIDER=azure` in `backend/.env` until Bedrock confirmed |
