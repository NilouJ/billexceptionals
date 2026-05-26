# 01 — Architecture

## TL;DR

A **real Strands multi-agent graph** with 5 nodes and 7 edges that screens a billing exception case and streams progress to a React UI over WebSocket. Skip behaviour lives in **edge conditions, not inside agents**. Four agents are deterministic Python; the fifth (Screening Outcome) is a real LLM call via Strands, with a deterministic Python fallback if the LLM call fails.

This is a faithful implementation of the architecture in `output/uc1-triage/01-functional-solution-design.md §4` from the proposal repo — minus the AWS managed-service surface (no AgentCore, no Lake Formation, no DynamoDB; everything is in-memory + CSVs for the prototype).

## The graph

```
case_intake_triage
   │
   ├── triage passed ───────────────────► precheck
   │                                          │
   │                                          ├── precheck passed ─────► groundrule
   │                                          │                              │
   │                                          │                              ├── workable ──► sop_context
   │                                          │                              │                   │
   │                                          │                              │                   ▼
   └─ excluded ─┐  ┌── blocked ───────────────┘                              └── unworkable ─┐  (always)
                │  │                                                                         │  │
                ▼  ▼                                                                         ▼  ▼
              screening_outcome  ◄────────────────────────────────────────────────────────────────
```

| Node | What it does | Decision codes |
|---|---|---|
| `case_intake_triage` | Fetches account; checks status, supply, complaints, holds | `EXCLUDE_TO_ONSHORE` / `PROCEED` |
| `precheck` | Fetches metering; checks deceased, life-support, hardship, comm failure | `BLOCK_TO_ONSHORE` / `PROCEED` |
| `groundrule` | Fetches agreement + service orders; validates billing period coverage | `UNWORKABLE_TO_ONSHORE` / `WORKABLE` |
| `sop_context` | Retrieves SOP rules for the exception type | `CONTEXT_ASSEMBLED` / `SOP_GAP` |
| `screening_outcome` | Synthesises the trace into a final recommendation | One of: `EXCLUDE_TO_ONSHORE`, `BLOCK_TO_ONSHORE`, `UNWORKABLE_TO_ONSHORE`, `NEEDS_MORE_DATA`, `WORKABLE` |

## Skip behaviour lives in edges, not agents

Each upstream node has **two outgoing edges** with mutually-exclusive conditions in `graph_topology.py`:

- `case_intake_triage → precheck` when `triage_excluded` is false
- `case_intake_triage → screening_outcome` when `triage_excluded` is true
- Same shape for `precheck → groundrule` vs `precheck → screening_outcome`
- Same shape for `groundrule → sop_context` vs `groundrule → screening_outcome`
- `sop_context → screening_outcome` unconditional

Conditions close over the shared `state` dict and read flags (`triage_excluded`, `precheck_blocked`, `groundrule_unworkable`) that agent functions set as they run. Strands evaluates conditions after each node completes, so flags are always fresh.

**Do not add `if state[context].get(...): return state` guards inside the agents** — they would duplicate edge logic and produce phantom `SKIPPED` trace entries.

## Layer boundaries (do not cross)

| File | Responsibility | Rule |
|---|---|---|
| `app.py` | FastAPI routes. WebSocket endpoint passes `websocket.send_json` as `send_event` into `run_screening_graph`. Loads `.env` at the very top so provider env vars are in `os.environ` before `graph_topology` imports. | Only HTTP/WS concerns here |
| `graph_runner.py` | Orchestration only. Owns the `stream_async` loop, the 0.6s UI pacing sleep, and translation from Strands events to WebSocket events. | No business logic |
| `graph_topology.py` | Declares the graph: instantiates nodes, declares the 7 edges with their condition closures, returns a `Graph`. Reads `LLM_PROVIDER` at import time to pick the outcome node type. | No agent logic |
| `graph_nodes.py` | `DeterministicNode` (wraps a `state -> state` function as `MultiAgentBase`) and `LLMOutcomeNode` (real Strands `Agent`, provider-agnostic via the factory). | No I/O outside the LLM call |
| `model_provider.py` | Factory: maps `LLM_PROVIDER` to a Strands model instance. | Only place that knows about cloud providers |
| `agents.py` | Pure-Python rule logic, `state -> state` functions. **Never touch FastAPI, WebSocket, or I/O directly.** Call into `tools.py` for data and append exactly one trace entry via `_trace()`. | Pure functions |
| `tools.py` | Data access layer. **The CSV reads here are the swap point for production**: replacing CSVs with Kraken GraphQL calls should not require any agent changes. Keep the return-dict shape stable. | Data only |
| `events.py` | Builds WebSocket event payloads. | Pure builders |
| `schemas.py` | `AGENT_ORDER`, `AGENT_LABELS`, `AGENT_STATUS`, `DECISIONS`. | No logic |

## Shared state shape

```python
state = {
    "case":    { case_id, account_number, esiid, exception_type, ... },
    "context": { data collected from tools, plus skip flags },
    "trace":   [ { agent_key, agent, decision, reasons, rule_hits, evidence }, ... ],
    "result":  None | { recommendation, reason_codes, rationale, next_action, summary },
}
```

Passed to every node via Strands' `invocation_state={"state": state}`. Single source of truth across the whole graph run.

## Rule tracking

Each trace entry carries a `rule_hits` list of `{ rule_id, reason }` pairs for rules that fired (e.g. `R01-01`, `R03-03`). The `_trace()` helper derives the flat `reasons` list from `rule_hits` automatically.

When adding a new rule: bump the rule ID in the agent's namespace (`R01-xx` for triage, `R02-xx` for precheck, etc.) and append `{rule_id, reason}` to `rule_hits` alongside the existing condition. Passing paths use `reasons=` directly and emit no `rule_hits`.

See [`03-rules-and-scenarios.md`](03-rules-and-scenarios.md) for the rule catalogue + Thursday extension plan.

## WebSocket event contract

The frontend (`useScreening` hook) is a passive consumer of three event types from `/ws/screen`:

- **`agent_status`** — `{ type, case_id, agent_key, agent, status: "running"|"done", decision?, reasons?, rule_hits?, evidence? }`
- **`final_result`** — `{ type, case_id, result, trace }`
- **`error`** — `{ type, case_id, message }`

The `evidence` field on `agent_status` carries per-agent context. For `screening_outcome` it includes:

| Field | Values | When |
|---|---|---|
| `source` | `llm_bedrock` / `llm_azure_foundry` / `deterministic_fallback` | Always |
| `model_id` | provider-specific model identifier | Always |
| `rationale` | LLM's 2–4 sentence explanation | LLM only |
| `next_action` | concrete next step | LLM only |
| `attempted_provider` | which provider was tried before fallback | Fallback only |
| `fallback_reason` | error message (first 200 chars) | Fallback only |

The frontend renders this as a corner badge on the agent card plus an inline amber error box on fallback.

When adding agents or changing decision codes, update `schemas.py` (`AGENT_ORDER`, `AGENT_LABELS`, `DECISIONS`) **and** mirror them in `frontend/src/constants/agents.js`. The frontend pre-renders all agent cards from `AGENT_ORDER` before any events arrive.

## Frontend architecture

`frontend/src/hooks/useScreening.js` is the single source of truth for run state. It opens the WebSocket, mutates `agents[]` / `trace[]` / `result` as events arrive, and exposes them to components. Components are dumb renderers — **do not put WebSocket logic in components**.

## Known gotchas

- **`exception_id` vs `case_id`** — `data/origin_exceptions.csv` names the ID column `exception_id`, but the graph and agents expect `case_id`. The frontend aliases this in `App.jsx:onRun` before sending. If you add a new entry point that feeds cases into the graph, you must do the same alias.
- **Agents are sync, runner is async** — Strands runs each node in its own asyncio task; inner agent functions stay sync. **Do not make agents async** — it breaks the layer boundary.
- **`LLM_PROVIDER` is read at import time** — `graph_topology.py` evaluates `os.environ` once when imported. `app.py` calls `load_dotenv()` BEFORE `from graph_runner import ...`, which is what allows `.env` to work. **Don't reorder those imports.**
- **Errors are silenced in the WebSocket handler** — `/ws/screen` catches all exceptions and sends a generic `error` event. When the graph appears to hang on the frontend, check the backend terminal for the real traceback.
- **Model IDs go stale** — Bedrock retires model versions; Foundry deployments can be deleted. Check the FALLBACK badge's inline error in the UI for the live error message.
- **CORS is OFF** — the slim `app.py` does not install `CORSMiddleware`. The frontend reaches the backend through the Vite proxy, so requests are same-origin. If anyone ever hits `:8000` from a browser on a different origin, add `CORSMiddleware` back.
- **`backend/.env` is gitignored and not baked into the Docker image** — pass env vars at runtime via `-e` flags instead.

## How this maps to the proposal architecture

| Proposal (`output/uc1-triage/01-functional-solution-design.md §4`) | Prototype |
|---|---|
| Screening Orchestrator (Super Agent, AgentCore + LangGraph) | `graph_topology.py` + `graph_runner.py` using Strands GraphBuilder |
| Triage Agent | `case_intake_triage_agent` in `agents.py` |
| Pre-check Agent | `precheck_agent` in `agents.py` |
| Ground-rule Agent | `groundrule_agent` in `agents.py` |
| Context + SOP Agent | `sop_context_agent` in `agents.py` |
| (new in prototype) Screening Outcome Agent | `LLMOutcomeNode` in `graph_nodes.py` |
| AWS Bedrock model gateway | `model_provider.py` (provider-agnostic — Bedrock OR Azure AI Foundry) |
| Kraken / MDH / OMG / Sidekick API layer | `tools.py` reads CSVs that mirror Kraken's shape |
| Panviva/KX SOP RAG via OpenSearch | `tools.py:get_sop()` — hard-coded dict (stretch goal: real RAG) |
| AgentCore Memory + DynamoDB session state | In-memory `state` dict per run |
| Databricks Delta Lake audit trail | `data/feedback_store.json` + the in-memory `trace` |
| Microsoft Teams HITL card | Front-end approval view (Day 1 work item) |
