# 02 — Provider Config (Bedrock vs Azure AI Foundry)

## The seam

Only **one** of the five graph nodes talks to an LLM: `screening_outcome` (the fifth, in `graph_nodes.py:LLMOutcomeNode`). The other four are deterministic Python. So provider-switching is **one env var + one factory function** — no agent code changes, no Strands changes, no UI changes beyond a badge colour.

The factory lives in `backend/model_provider.py`. It maps the `LLM_PROVIDER` env var to a Strands-compatible model instance.

| `LLM_PROVIDER` | Outcome node uses | When to use |
|---|---|---|
| `bedrock` | AWS Bedrock — Claude Sonnet 4.5 via Strands `BedrockModel` | SP51 target platform; primary choice once AWS access lands |
| `azure` | Azure AI Foundry — Claude via Strands `AnthropicModel` pointed at Foundry's Anthropic-compatible endpoint | Hackathon-week fallback; while AWS access is being provisioned |
| `deterministic` *(default)* | Python rules in `agents.py:case_screening_outcome_agent` | Local dev without cloud creds; CI; offline demos |

Default is `deterministic` so a fresh clone runs with zero configuration.

## Setup — AWS Bedrock

```bash
cp backend/.env.bedrock.example backend/.env
```

Fill in:

```bash
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
AWS_REGION=us-east-1
# Plus AWS creds via env vars / ~/.aws / instance profile
```

Test access:

```bash
python -c "from strands import Agent; from strands.models.bedrock import BedrockModel; \
print(Agent(model=BedrockModel(model_id='us.anthropic.claude-sonnet-4-5-20250929-v1:0', region_name='us-east-1'))('PONG'))"
```

If you see `ResourceNotFoundException: ... marked by provider as Legacy`, the model needs reactivation in the Bedrock console (Model Access → re-enable). The prototype handles this gracefully — it falls back to the deterministic outcome and shows a FALLBACK badge with the live error in the UI.

## Setup — Azure AI Foundry

```bash
cp backend/.env.azure.example backend/.env
```

Fill in:

```bash
LLM_PROVIDER=azure
AZURE_AI_FOUNDRY_ENDPOINT=https://<your-resource>.services.ai.azure.com/anthropic/
AZURE_AI_FOUNDRY_API_KEY=<your-key>
AZURE_AI_FOUNDRY_DEPLOYMENT=<your-claude-deployment-name>
```

**Where to find each value in Azure AI Foundry:**

| Env var | Foundry UI location |
|---|---|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Resource → **Keys and Endpoint** → Endpoint URL. **MUST end with `/anthropic/`** — Foundry's Anthropic-compatible passthrough |
| `AZURE_AI_FOUNDRY_API_KEY` | Resource → **Keys and Endpoint** → KEY 1 or KEY 2 |
| `AZURE_AI_FOUNDRY_DEPLOYMENT` | Project → **Deployments** → your Claude deployment's **Name** (e.g. `claude-sonnet-4-6`) |

**Under the hood:** we use Strands' `AnthropicModel` with `base_url` overridden. The standard Anthropic Python SDK speaks Foundry's `/anthropic/` route natively — no LiteLLM layer needed.

Test access:

```bash
python -c "
import os; os.environ.setdefault('LLM_PROVIDER','azure');
from model_provider import get_outcome_model
from strands import Agent
m = get_outcome_model()
print(Agent(model=m)('PONG — say hello'))"
```

(Run from `backend/` with `.env` already populated.)

## Switching providers live

The provider is read at **import time** in `graph_topology.py`. To switch:

1. Stop the backend (`Ctrl+C` the uvicorn process).
2. Edit `backend/.env` — change `LLM_PROVIDER`.
3. Restart uvicorn.

The frontend doesn't need a restart — it'll see the new `evidence.source` on the next case run and re-colour the badge accordingly.

**Do not** try to switch providers mid-process via env-var mutation — Strands caches the model on the `LLMOutcomeNode` instance after the first call (`_ensure_agent`), and `graph_topology.py` only checks `LLM_PROVIDER` once on module load.

## What happens when the LLM fails

Any failure in the LLM path — wrong creds, throttle, retired model id, malformed JSON output, network blip — is caught in `LLMOutcomeNode.invoke_async()`. The node:

1. Runs `case_screening_outcome_agent(state)` (the deterministic fallback)
2. Stamps the latest trace entry's `evidence`:
   - `source = "deterministic_fallback"`
   - `attempted_provider = "llm_bedrock"` or `"llm_azure_foundry"` (whichever was tried)
   - `model_id = <whatever provider_model_id() returns>`
   - `fallback_reason = <first 200 chars of the exception>`
3. Returns `Status.COMPLETED` so the rest of the graph and the frontend behave as if the LLM had succeeded.

The UI surfaces this as the amber FALLBACK badge plus an inline error message:

> ⚠ Azure AI Foundry error — using deterministic fallback: \<reason\>

**Implication for the demo:** the live demo can never break on an LLM failure — the worst case is a FALLBACK badge that the demo driver can either narrate ("note our graceful degradation") or hide (run the same case again after fixing the env).

## Frontend badge mapping

`frontend/src/components/AgentCard.jsx` maps `evidence.source` to one of three badges:

| `evidence.source` value | Badge label | Colour |
|---|---|---|
| `llm_bedrock` | "Claude · Bedrock" | Blue (`#3b82f6`) |
| `llm_azure_foundry` | "Claude · Azure" | Purple (`#7c3aed`) |
| `deterministic_fallback` | "FALLBACK" | Amber (`#f59e0b`) |
| (anything else, including `"deterministic"`) | no badge | — |

## Adding a new provider

If we ever want Anthropic direct, Google Vertex, OpenAI direct, or a custom endpoint:

1. Add a new constant + valid value in `model_provider.py` (e.g. `PROVIDER_ANTHROPIC = "anthropic"`).
2. Add a new branch in `get_outcome_model()` returning the relevant Strands model class.
3. Add a tag in `provider_source_tag()` (e.g. `"llm_anthropic"`).
4. Add a row in `frontend/src/components/AgentCard.jsx:SOURCE_BADGES`.
5. Add a `.env.<provider>.example` template.
6. Add the row to this file's "Setup" section.

That's it. No agent code changes, no graph topology changes.

## How this maps to the proposal

The proposal's `output/uc1-triage/01-functional-solution-design.md §4.1` mandates **AWS Bedrock + AgentCore** as the agent runtime — that remains the production target. The provider abstraction in this prototype is **not** a deviation from that target; it's a hackathon-week de-risking move:

- **If AWS Bedrock access lands by Thursday:** the demo runs on Bedrock end-to-end. Identical to the proposed production architecture.
- **If AWS Bedrock access is delayed:** the demo runs on Azure AI Foundry — same Claude model family, same Strands code path, same agent logic. The architecture story stays intact ("we're showing the screening funnel; in production this runs on Bedrock per SP51").

Frame it for the judges as deliberate architecture portability, not a workaround. **Same model, two clouds — Origin's choice.**
