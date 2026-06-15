# Bill Exceptionals — UC-1 Triage Prototype

Hackathon build of the **Origin Energy UC-1 Billing Exception Triage** automation, anchored to the SP51 Agentic Enterprise solution architecture. This repo extends the team's local prototype with provider-agnostic LLM support (AWS Bedrock or Azure AI Foundry) and the rule / scenario / HITL coverage from the original UC-1 Functional Solution Design.

## What this is

A real Strands multi-agent graph that screens billing exception cases through five agents and streams progress to a React UI over WebSocket. **Same prototype, two clouds** — the LLM-powered outcome agent runs on Bedrock (SP51 target platform) or Azure AI Foundry depending on a single env var.

The architecture is the one Accenture proposed in `/output/uc1-triage/01-functional-solution-design.md` from the proposal engagement — Triage → Pre-check → Ground-rule → Context+SOP → Screening Outcome — implemented as a Strands `GraphBuilder` with conditional edges.

## Quickstart (5 minutes)

### 1. Backend — Python 3.11+

```bash
# From the repo root
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 2. Pick a provider for the outcome agent

```bash
# Option A — Deterministic (no cloud creds needed, agents 1-4 run as normal,
# agent 5 uses Python rules instead of an LLM). Best for first-run smoke test.
echo "LLM_PROVIDER=deterministic" > backend/.env

# Option B — Azure AI Foundry (Claude on Microsoft hosting). Recommended for
# the hackathon while AWS access is still being provisioned.
cp backend/.env.azure.example backend/.env
# Edit backend/.env with your Foundry endpoint + key + deployment name.

# Option C — AWS Bedrock (SP51 target platform).
cp backend/.env.bedrock.example backend/.env
# Edit backend/.env with your AWS region + model id, ensure AWS creds are loaded.
```

See [`docs/02-provider-config.md`](docs/02-provider-config.md) for the full env var matrix and how to switch live.

### 3. Run backend + frontend

```bash
# Terminal 1 — Backend on :8000
cd backend
uvicorn app:app --reload --port 8000

# Terminal 2 — Frontend on :5173 (proxies /api and /ws to :8000)
cd frontend
npm install                          # first time only
npm run dev
```

Open <http://localhost:5173>, pick a case from the sidebar, hit **Run Screening**. The five agent cards stream live as the Strands graph executes.

### 4. (Optional) Curl-test the synchronous endpoint

```bash
curl -X POST localhost:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"case_id":"EX-TEST","account_number":"A-10000000","esiid":"...","exception_type":"UNBILLED"}'
```

## Repo layout

```
billexceptionals/
├── README.md                  ← you are here
├── HACKATHON.md               ← Thu/Fri plan + demo narrative
├── CLAUDE.md                  ← AI assistant context (used by Claude Code)
├── docs/
│   ├── 01-architecture.md     ← 5-node Strands graph topology, layer boundaries
│   ├── 02-provider-config.md  ← Bedrock vs Azure AI Foundry setup + switching
│   ├── 03-rules-and-scenarios.md  ← Current rules + proposal mapping (PC/GR/SCEN)
│   └── 04-demo-narrative.md   ← The 5-min demo flow for Origin judges
├── backend/
│   ├── app.py                 ← FastAPI entry (3 routes)
│   ├── graph_topology.py      ← Strands GraphBuilder, conditional edges
│   ├── graph_nodes.py         ← DeterministicNode + LLMOutcomeNode wrappers
│   ├── graph_runner.py        ← stream_async loop + event translation
│   ├── model_provider.py      ← Bedrock / Azure / deterministic factory
│   ├── agents.py              ← Pure-Python rule logic for agents 1-4 + fallback 5
│   ├── tools.py               ← CSV data access (swap point for Kraken in prod)
│   ├── schemas.py             ← AGENT_ORDER, AGENT_LABELS, DECISIONS
│   ├── events.py              ← WebSocket event payload builders
│   ├── data/                  ← 10 CSVs mocking Kraken + 100 exception cases
│   ├── .env.bedrock.example   ← Template for AWS Bedrock setup
│   └── .env.azure.example     ← Template for Azure AI Foundry setup
└── frontend/
    └── src/                   ← React + Vite, talks to backend over /ws/screen
```

## Where the proposal IP lives

The functional design, delivery plan, production plan, AI governance framework, and the proposal deck for UC-1 Triage are in the **proposal repo**, not this one:

- `C:\Projects\origin\output\uc1-triage\01-functional-solution-design.md` — the design this prototype implements
- `C:\Projects\origin\output\uc1-triage\02-delivery-plan.md` — 8-week sprint plan + roles
- `C:\Projects\origin\output\uc1-triage\03-production-plan.md` — go-live + scale operations plan
- `C:\Projects\origin\output\uc1-triage\04-ai-governance-framework.md` — RACI, ethics, audit
- `C:\Projects\origin\output\uc1-triage\bound\Origin_UC1_Proposal_Deck_Native.pptx` — slides to recycle

[`docs/03-rules-and-scenarios.md`](docs/03-rules-and-scenarios.md) maps the prototype's current rule IDs (R01-xx, R02-xx, etc.) back to the proposal's PC-01..03 / GR-01..09 / SCEN-01..09 catalogue so the team knows which gaps to close on Thursday.

## What's next

See [`HACKATHON.md`](HACKATHON.md) for the Thursday-Friday work plan, role splits, and demo flow. The pre-hackathon abstraction (provider-agnostic LLM, env templates, docs structure) is done — the squad can clone and run immediately.

## Need help

| Topic | Owner |
|---|---|
| Backend + Strands graph | Squad backend lead |
| Frontend + UI state | Squad frontend lead |
| Bedrock / Azure provisioning | Squad infra lead |
