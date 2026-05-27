# 05 — Success Criteria & Why We Built What We Built

This doc is the squad's **north star** for the hackathon. Read this first — `HACKATHON.md` is the work plan; this doc is *what we're aiming for and why*.

---

## The five things that make this a win

Anchored to the UC-1 vision and what Origin internal judges will reward:

| # | Success criterion | Why it matters | How we verify Friday afternoon |
|---|---|---|---|
| **S1** | **Conversational interaction** with the case | Origin's analysts don't think in JSON traces — they think in questions. *"Why was this excluded? Show me the meter reads. What should I do next?"* The chat makes the multi-agent output legible to a human. | Pick any case → Run Screening → ask "Why?" in the chat → get a plain-English answer that cites rule IDs and underlying data |
| **S2** | **Clear data checks + clear messages** | Every exclusion has to be defensible. An onshore analyst receiving a returned case needs to know exactly which rule fired, what data triggered it, and where to verify. | Click any agent card → expand → see the rule chips and the evidence dict. Click a rule chip → hover tooltip with the human reason. |
| **S3** | **Guided UX** | Origin's billing analysts handle 24k+ exceptions per day. Speed comes from the UI telling them what to do, not making them figure it out. Chat is one source of guidance; next-action chips are another. | After every screening run, the analyst sees: 3 starter questions for the assistant, 3 next-action buttons sized to the outcome, the SOP reference with key steps, and recommended actions. |
| **S4** | **Branded as Origin** | This is a working Origin product, not a generic React template. Visual identity carries credibility — judges read "this could ship Monday" or "this is a college hackathon project" within 10 seconds. | Open the app — Origin logo top-left, Origin red as the primary accent, clean white sidebar/panels, "Origin · Bill Exceptions Assistant" in the browser tab. |
| **S5** | **Production-credible** for the 13-week build | The whole point is to prove the SP51 architecture works *and* hand off a starting point. Engineering team should be able to clone this Monday and start Sprint 1 without re-architecting. | Re-read [`01-architecture.md`](01-architecture.md) — the layer boundaries hold, the seams (provider abstraction, tools.py data swap, deterministic fallback) are honoured. README lets a new joiner run the stack in 5 minutes. |

If any one of these is missing Friday afternoon, the demo is incomplete.

---

## What we deliberately kept *out* of scope

So the squad doesn't get pulled sideways:

- **No real Kraken integration.** `tools.py` reads synthetic CSVs that mirror Kraken's shape. Swap is one file change — that's the design.
- **No persistent chat history.** Per-case, in-process. Production = DynamoDB + AgentCore Memory. Out of scope for hackathon.
- **No real authn/authz.** Localhost-only. Production = AWS IAM + AgentCore Identity.
- **No batch scheduler.** The `/screen/batch` endpoint runs all 100 cases on-demand for the demo. Production = EventBridge → Lambda nightly.
- **No real SOP RAG.** The `scenarios.py` module has hardcoded SOP references. Production = Bedrock Knowledge Bases on Panviva/KX corpus.
- **No deck or pitch slides in this repo.** Those live in the proposal repo at `C:\Projects\origin\output\uc1-triage\slides\`.

These aren't bugs. They're the right scope for a 2-day demo that *credibly* shows what the 13-week build delivers.

---

## How the hackathon work ladders to success

Every work item in `HACKATHON.md` maps to one or more success criteria:

| Work item | S1 chat | S2 data | S3 guided | S4 Origin | S5 prod-credible |
|---|---|---|---|---|---|
| W1 — Origin branding pass | | | | ✅ | |
| W2 — Chat backend (Strands `/ws/chat`) | ✅ | | ✅ | | |
| W3 — Chat UI panel | ✅ | | ✅ | | |
| W4 — Data drill-down on agent cards | | ✅ | | | |
| W5 — Next-action chips | | | ✅ | | |
| W6 — Demo data fixes | | | | | ✅ |
| T1 — Rule catalogue extension (PMD, OOC>$5k) | | ✅ | | | ✅ |
| T2 — Scenario classification SCEN-01..09 | | | ✅ | | ✅ |
| T3 — Case-pack JSON output | ✅ | ✅ | ✅ | | ✅ |
| T4 — Team Leader HITL view | | | ✅ | | ✅ |
| T5 — Batch endpoint | | | | | ✅ |
| T6 — KPI panel | | | ✅ | | |
| T7 — SOP RAG (stretch) | ✅ | | | | ✅ |

Translation: skipping any one of these reduces the score on at least one success criterion. Cut order is documented in `HACKATHON.md` — drop the *least* multi-S items first.

---

## The five-minute demo flow that proves all five

See [`04-demo-narrative.md`](04-demo-narrative.md) for the beat-by-beat. The hooks per S-criterion:

| Demo beat | Proves |
|---|---|
| Open the app — Origin logo, palette, header | S4 |
| Pick a case, Run Screening → 5 cards stream | S5 (real Strands graph, real WebSocket) |
| Click an agent card → drill-down with evidence | S2 |
| FinalResult shows scenario + SOP + recommended actions | S3 |
| Click "Ask the assistant" → chat-input focuses | S3 |
| Type "Why was this excluded?" → Claude streams back a plain-English answer | S1 |
| Click a next-action chip → routes to onshore queue | S3 |
| (Day 2) Hit Run Batch → funnel + KPI numbers | S5 (volume credibility) |

If a judge walks away saying *"the chat felt like a real co-pilot, and the architecture looks shippable"* — we won.

---

## Pointers for the squad

- **`README.md`** — the only doc you need to clone + run the stack
- **`HACKATHON.md`** — Thursday and Friday work plan, roles, cut list, risks
- **`CLAUDE.md`** — context for Claude Code (or any AI assistant) editing this codebase
- **`docs/01-architecture.md`** — the 5-agent graph, layer boundaries, gotchas
- **`docs/02-provider-config.md`** — Bedrock vs Azure AI Foundry env setup
- **`docs/03-rules-and-scenarios.md`** — rule catalogue, SCEN-01..09 mapping
- **`docs/04-demo-narrative.md`** — the 5-minute judging-slot script
- **`docs/05-success-criteria.md`** — this file. The north star.

Proposal IP is at `C:\Projects\origin\output\uc1-triage\` — separate repo, holds the FSD, Delivery Plan, Production Plan, AI Governance framework, and the proposal deck. **Reference, don't copy.** This prototype implements the FSD §4 architecture.
