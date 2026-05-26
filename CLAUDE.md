# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This is the **UC-1 Billing Exception Triage** hackathon prototype for Origin Energy, extending the team's local prototype with provider-agnostic LLM support and the rule/scenario coverage from the UC-1 Functional Solution Design.

For team-facing docs, start at `README.md` and `HACKATHON.md`. For architecture deep-dives, see `docs/`.

## Commands

Backend and frontend run as **two separate processes**. Vite proxies `/api/*` → `:8000` and `/ws/*` → `ws://:8000`, so the frontend talks to the backend through `localhost:5173` only.

```bash
# Backend (FastAPI, port 8000)
source .venv/bin/activate            # PowerShell: .venv\Scripts\Activate.ps1
cd backend
uvicorn app:app --reload --port 8000

# Backend deps (uses the .venv at repo root, not inside backend/)
pip install -r backend/requirements.txt

# Frontend (Vite + React, port 5173)
cd frontend
npm install                          # first time only
npm run dev

# Test the graph synchronously, bypassing the WebSocket
curl -X POST localhost:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"case_id":"EX-TEST","account_number":"A-10000000","esiid":"...","exception_type":"UNBILLED"}'
```

The outcome agent's LLM provider is chosen at startup via `LLM_PROVIDER`:

```bash
# Deterministic (default — no cloud creds needed)
LLM_PROVIDER=deterministic uvicorn app:app --reload --port 8000

# AWS Bedrock (SP51 target platform)
cp backend/.env.bedrock.example backend/.env   # then edit values
uvicorn app:app --reload --port 8000

# Azure AI Foundry (hackathon-week alternative)
cp backend/.env.azure.example backend/.env     # then edit values
uvicorn app:app --reload --port 8000
```

There are no tests or linters configured. The `.venv` lives at the repo root, not inside `backend/`. `backend/.env` (gitignored) is loaded by `app.py` via `load_dotenv()` BEFORE importing the graph — so anything in `.env` is in `os.environ` by the time `graph_topology.py` reads `LLM_PROVIDER`.

## Architecture

This is a **real Strands multi-agent graph** that screens billing exceptions and streams progress over WebSocket. The graph has 5 nodes, 7 edges, and conditional edge traversal — skipping is encoded in the topology, not inside the agents.

See `docs/01-architecture.md` for the full architecture writeup. The short version is below.

### The graph contract

`backend/graph_topology.py` builds a Strands `GraphBuilder` graph. `backend/graph_runner.py` runs it via `graph.stream_async(...)` and forwards Strands' native events to the WebSocket:

```python
state = { "case": {...}, "context": {}, "trace": [], "result": None }
graph = build_screening_graph(state)
async for event in graph.stream_async(task="screen_case", invocation_state={"state": state}):
    # event["type"] is "multiagent_node_start" | "multiagent_node_stop" | "multiagent_result"
    ...
```

The 5 nodes (declared in order in `backend/schemas.py:AGENT_ORDER`):

1. **`case_intake_triage`** — fetches account, checks status/supply/complaints/holds → `EXCLUDE_TO_ONSHORE` or `PROCEED`
2. **`precheck`** — fetches metering, checks deceased/life-support/hardship/comm-failure → `BLOCK_TO_ONSHORE` or `PROCEED`
3. **`groundrule`** — fetches agreement + service orders, validates billing period coverage → `UNWORKABLE_TO_ONSHORE` or `WORKABLE`
4. **`sop_context`** — retrieves SOP rules for the exception type → `CONTEXT_ASSEMBLED` or `SOP_GAP`
5. **`screening_outcome`** — aggregates trace into final recommendation, writes `state["result"]`. Either deterministic Python OR a real Strands LLM agent (Bedrock or Azure AI Foundry) — see `model_provider.py`.

### Skip behaviour lives in edges, not agents

Each upstream node has TWO outgoing edges with mutually exclusive conditions defined in `graph_topology.py`:

- `case_intake_triage → precheck` when `triage_excluded` is false
- `case_intake_triage → screening_outcome` when `triage_excluded` is true
- same shape for `precheck → groundrule` vs `precheck → screening_outcome`
- same shape for `groundrule → sop_context` vs `groundrule → screening_outcome`
- `sop_context → screening_outcome` unconditional

Conditions close over the shared `state` dict and read flags (`triage_excluded`, `precheck_blocked`, `groundrule_unworkable`) that the agent functions set as they run. Strands evaluates conditions after each node completes, so flags are always fresh. **Do not re-add "if state[context].get(...): return state" guards inside the agents — they would duplicate edge logic and produce phantom `SKIPPED` trace entries.**

### Layer boundaries (do not cross)

- `app.py` — FastAPI routes. The `/ws/screen` endpoint passes `websocket.send_json` as `send_event` into `run_screening_graph`. Loads `.env` at the very top so the provider env vars are in `os.environ` before `graph_topology` imports.
- `graph_runner.py` — orchestration only. Owns the `stream_async` loop, the 0.6s sleep for UI pacing, and translation from Strands events to WebSocket events.
- `graph_topology.py` — declares the graph: instantiates nodes, declares the 7 edges with their condition closures, returns a `Graph`. Reads `LLM_PROVIDER` at import time to pick the outcome node type.
- `graph_nodes.py` — `DeterministicNode` (wraps a `state -> state` function as `MultiAgentBase`) and `LLMOutcomeNode` (real Strands `Agent`, provider-agnostic via the factory, with deterministic fallback).
- `model_provider.py` — **the only file that knows about cloud providers**. Maps `LLM_PROVIDER` to a Strands model instance (`BedrockModel` for AWS, `AnthropicModel` with custom `base_url` for Foundry's Anthropic-compatible endpoint). Adding a new provider = one new branch here.
- `agents.py` — pure-Python rule logic, `state -> state` functions. **Never touch FastAPI, WebSocket, or I/O directly.** Call into `tools.py` for data and append exactly one trace entry via `_trace()`.
- `tools.py` — data access layer. **The CSV reads here are the swap point for production**: replacing CSVs with Kraken GraphQL calls should not require any agent changes. Keep the return-dict shape stable.
- `events.py` — builds WebSocket event payloads. `schemas.py` holds the agent order, labels, status enum, and decision codes.

### Rule tracking

Each trace entry carries a `rule_hits` list of `{ rule_id, reason }` pairs for rules that fired (e.g. `R01-01`, `R03-03`). The `_trace()` helper derives the flat `reasons` list from `rule_hits` automatically. When adding a new rule: bump the rule ID in the agent's namespace (`R01-xx` for triage, `R02-xx` for precheck, etc.) and append `{rule_id, reason}` to `rule_hits` alongside the existing condition. Passing paths use `reasons=` directly and emit no `rule_hits`.

See `docs/03-rules-and-scenarios.md` for the current rule catalogue and the gaps vs. the proposal's PC-01..03 / GR-01..09 catalogue.

### WebSocket event contract

The frontend (`useScreening` hook) is a passive consumer of three event types from `/ws/screen`:

- `agent_status` — `{ type, case_id, agent_key, agent, status: "running"|"done", decision?, reasons?, rule_hits?, evidence? }`
- `final_result` — `{ type, case_id, result, trace }`
- `error` — `{ type, case_id, message }`

The `evidence` field on `agent_status` carries per-agent context. For `screening_outcome` it includes:

- `source` — `"llm_bedrock"` | `"llm_azure_foundry"` | `"deterministic_fallback"`
- `model_id` — provider-specific model identifier
- `rationale`, `next_action`, `raw_reason_codes` — LLM output (when LLM ran)
- `attempted_provider`, `fallback_reason` — only on `"deterministic_fallback"`

The frontend renders this as a corner badge on the agent card (Bedrock blue / Azure purple / Fallback amber) plus an inline amber error box on fallback.

When adding agents or changing decision codes, update `schemas.py` (`AGENT_ORDER`, `AGENT_LABELS`, `DECISIONS`) **and** mirror them in `frontend/src/constants/agents.js`. The frontend pre-renders all agent cards from `AGENT_ORDER` before any events arrive.

### LLM outcome agent — provider-agnostic

`graph_nodes.py:LLMOutcomeNode` calls a Strands `Agent` whose model is built by `model_provider.get_outcome_model()`. The factory branches on `LLM_PROVIDER`:

- `bedrock` → `strands.models.bedrock.BedrockModel` with `BEDROCK_MODEL_ID` + `AWS_REGION`
- `azure` → `strands.models.anthropic.AnthropicModel` with `base_url` pointed at Foundry's `/anthropic/` endpoint
- `deterministic` → `LLMOutcomeNode` is not used at all; `graph_topology.py` picks the deterministic node instead

The system prompt asks for `recommendation`, `reason_codes` (3-6 items), `rationale`, `next_action`, and `summary` as a single JSON object (no Pydantic — we parse with `json.loads` + a small fence-stripping helper). On ANY failure (no creds, throttle, bad JSON, retired model id), the node calls `case_screening_outcome_agent(state)` as a fallback and stamps `evidence.source = "deterministic_fallback"` plus `evidence.attempted_provider` and `evidence.fallback_reason`. So the demo never breaks; the UI shows a FALLBACK badge instead of LLM.

Env vars (read by `model_provider`):
- `LLM_PROVIDER` — `bedrock` | `azure` | `deterministic` (default: `deterministic`)
- Bedrock: `BEDROCK_MODEL_ID`, `AWS_REGION`
- Azure: `AZURE_AI_FOUNDRY_ENDPOINT` (must end with `/anthropic/`), `AZURE_AI_FOUNDRY_API_KEY`, `AZURE_AI_FOUNDRY_DEPLOYMENT`

See `docs/02-provider-config.md` for setup walkthroughs of both providers.

### Frontend architecture

`frontend/src/hooks/useScreening.js` is the single source of truth for run state. It opens the WebSocket, mutates `agents[]` / `trace[]` / `result` as events arrive, and exposes them to components. Components are dumb renderers — do not put WebSocket logic in components.

## Known gotchas

- **`exception_id` vs `case_id`**: `data/origin_exceptions.csv` names the ID column `exception_id`, but the graph and agents expect `case_id`. The frontend aliases this in `App.jsx:onRun` before sending. If you add a new entry point that feeds cases into the graph, you must do the same alias.
- **Agents are sync, runner is async**: Strands runs each node in its own asyncio task; the inner agent functions stay sync. Do not make agents async — it breaks the layer boundary.
- **`LLM_PROVIDER` is read at import time**: `graph_topology.py` evaluates `os.environ` once when imported. `app.py` calls `load_dotenv()` BEFORE `from graph_runner import ...`, which is what allows `.env` to work. Don't reorder those imports.
- **Errors are silenced in the WebSocket handler**: `/ws/screen` catches all exceptions and sends a generic `error` event. When the graph appears to hang on the frontend, check the backend terminal for the real traceback.
- **Model IDs go stale**: Bedrock retires model versions; Foundry deployments can be deleted. Check the FALLBACK badge's inline error in the UI, or run a smoke-test query against the provider before the demo.
- **CORS is OFF**: the slim `app.py` does not install `CORSMiddleware`. The frontend reaches the backend through the Vite proxy, so requests are same-origin. If anyone ever hits `:8000` from a browser on a different origin, add `CORSMiddleware` back.
- **`backend/.env` is gitignored and not baked into the Docker image** (excluded via `backend/.dockerignore`). Pass env vars at runtime via `-e` flags instead.

## Proposal IP — where to look

The UC-1 Triage Functional Solution Design, Delivery Plan, Production Plan, AI Governance Framework, and the proposal deck are in a **separate repo** at `C:\Projects\origin\output\uc1-triage\`. This prototype implements the architecture in `01-functional-solution-design.md §4`. The rule catalogue mapping is in `docs/03-rules-and-scenarios.md` of this repo.

Don't try to read those files via paths in this repo — they don't live here. The team has been pointed at the proposal repo separately via `HACKATHON.md`.
