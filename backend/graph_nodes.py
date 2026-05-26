"""
graph_nodes.py — Strands graph node wrappers.

Two node types live here:

  1. DeterministicNode  — wraps a plain Python `state -> state` function
                          (used for triage, precheck, groundrule, sop_context).
  2. LLMOutcomeNode     — a REAL Strands Agent backed by a configurable LLM
                          provider (AWS Bedrock or Azure AI Foundry) that reads
                          the trace from earlier nodes and produces the final
                          recommendation. Falls back to the deterministic
                          outcome on ANY failure so the demo never breaks.

Provider selection lives in `model_provider.py`. This file is provider-agnostic
— it asks the factory for a model and trusts Strands to do the rest.

The shared mutable `state` dict (case / context / trace / result) is passed
to every node via Strands' `invocation_state` so all nodes share one view.
"""

import json
import time

from strands import Agent
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status

from agents import _trace, case_screening_outcome_agent
from model_provider import get_outcome_model, provider_model_id, provider_source_tag
from schemas import AGENT_LABELS


# ──────────────────────────────────────────────────────────────────────────────
# Node 1: deterministic wrapper for the first 4 agents
# ──────────────────────────────────────────────────────────────────────────────

class DeterministicNode(MultiAgentBase):
    """Wraps a sync `state -> state` function as a Strands graph node."""

    def __init__(self, node_id: str, fn):
        self.id = node_id
        self._fn = fn

    async def invoke_async(self, task=None, invocation_state=None, **kwargs) -> MultiAgentResult:
        invocation_state = invocation_state or {}
        state = invocation_state["state"]

        started = time.monotonic()
        try:
            self._fn(state)
            status = Status.COMPLETED
            payload = MultiAgentResult(status=status)
        except Exception as exc:
            status = Status.FAILED
            payload = exc

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return MultiAgentResult(
            status=status,
            results={
                self.id: NodeResult(
                    result=payload,
                    status=status,
                    execution_time=elapsed_ms,
                    execution_count=1,
                ),
            },
            execution_time=elapsed_ms,
            execution_count=1,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Node 2: real LLM-powered outcome agent (Bedrock or Azure AI Foundry)
# ──────────────────────────────────────────────────────────────────────────────

ALLOWED_RECOMMENDATIONS = {
    "RETURN_TO_ONSHORE_EXCLUDED",
    "RETURN_TO_ONSHORE_BLOCKED",
    "RETURN_TO_ONSHORE_UNWORKABLE",
    "RETURN_TO_ONSHORE_NEEDS_SOP",
    "WORKABLE",
}


_OUTCOME_SYSTEM_PROMPT = """You are the Case Screening Outcome agent for an Australian energy retailer's
billing-exception workflow. Four upstream agents have already inspected the case
(triage, pre-check, ground-rule, SOP context). Their findings sit in the trace
the user will give you.

Your job: read the trace and emit ONE final recommendation with rich reasoning.
Do not invent new rules — but DO explain each one that fired in plain English.
Honor the trace:

  - If triage decided RETURN_TO_ONSHORE_EXCLUDED   → recommend RETURN_TO_ONSHORE_EXCLUDED
  - If pre-check decided RETURN_TO_ONSHORE_BLOCKED  → recommend RETURN_TO_ONSHORE_BLOCKED
  - If ground-rule decided RETURN_TO_ONSHORE_UNWORKABLE → recommend RETURN_TO_ONSHORE_UNWORKABLE
  - If SOP context returned SOP_GAP        → recommend RETURN_TO_ONSHORE_NEEDS_SOP
  - Otherwise (all earlier nodes proceeded) → recommend WORKABLE

REASONING REQUIREMENTS:
  - `reason_codes` MUST contain 3 to 6 items.
  - Each `reason_code` is ONE short sentence (15-25 words) that ties a specific
    rule_id from the trace to its business consequence. Format: "Rxx-yy: <explanation>".
  - If a node decided PROCEED/WORKABLE/CONTEXT_ASSEMBLED, include a positive
    `reason_code` summarising why that stage passed.
  - `rationale` is 2-4 sentences walking the analyst through the decision path:
    which agent triggered the conclusion, what evidence sealed it, and what to
    do next.
  - `next_action` is the single concrete next step (e.g. "Forward to onshore
    billing for manual review of agreement coverage.").
  - `summary` is one sentence aimed at the billing analyst.

OUTPUT FORMAT — return ONLY a single JSON object, no prose, no code fences:
{
  "recommendation": "<one of: RETURN_TO_ONSHORE_EXCLUDED | RETURN_TO_ONSHORE_BLOCKED | RETURN_TO_ONSHORE_UNWORKABLE | RETURN_TO_ONSHORE_NEEDS_SOP | WORKABLE>",
  "reason_codes":   ["Rxx-yy: ...", "Rxx-yy: ...", ...],
  "rationale":      "<2-4 sentence explanation of the decision path>",
  "next_action":    "<one concrete next step>",
  "summary":        "<one sentence aimed at the billing analyst>"
}
"""


def _extract_json_object(text: str) -> dict:
    """
    Pull the first JSON object out of an LLM response. Tolerant of:
      - leading/trailing prose
      - markdown code fences (```json ... ```)
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
    first = s.find("{")
    last  = s.rfind("}")
    if first == -1 or last == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(s[first:last + 1])


class LLMOutcomeNode(MultiAgentBase):
    """
    The 5th graph node — a real Strands Agent on a configurable LLM provider.

    Flow:
      1. Read state["trace"] (decisions from the first 4 nodes).
      2. Build a compact prompt and call the LLM via a Strands Agent.
      3. The model returns a JSON object as plain text; we parse with json.loads.
      4. Validate `recommendation` is in the allowed set.
      5. Write back into state["result"] and append a trace entry.
      6. On ANY failure (no creds, throttle, bad JSON, retired model id, ...)
         fall back to the deterministic outcome so the demo never breaks. The
         UI surfaces this via a FALLBACK badge and an inline error.

    Configuration is loaded from env vars by `model_provider.get_outcome_model()`
    — see backend/.env.bedrock.example and backend/.env.azure.example.
    """

    def __init__(self, node_id: str = "screening_outcome"):
        self.id = node_id
        # Lazy construction: don't fail import if creds aren't configured.
        self._agent: Agent | None = None

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            model = get_outcome_model()
            self._agent = Agent(model=model, system_prompt=_OUTCOME_SYSTEM_PROMPT)
        return self._agent

    def _build_prompt(self, state: dict) -> str:
        """Compact the trace so the LLM only sees what it needs."""
        case = state["case"]
        compact_trace = [
            {
                "agent":    AGENT_LABELS.get(t["agent_key"], t["agent_key"]),
                "decision": t["decision"],
                "reasons":  t.get("reasons", []),
                "rule_ids": [h["rule_id"] for h in t.get("rule_hits", [])],
            }
            for t in state["trace"]
        ]
        return (
            f"Case ID: {case.get('case_id')}\n"
            f"Account:  {case.get('account_number')}\n"
            f"Exception type: {case.get('exception_type')}\n\n"
            f"Trace from earlier agents:\n{json.dumps(compact_trace, indent=2)}\n\n"
            "Return the final recommendation now as a single JSON object."
        )

    async def invoke_async(self, task=None, invocation_state=None, **kwargs) -> MultiAgentResult:
        invocation_state = invocation_state or {}
        state = invocation_state["state"]
        started = time.monotonic()

        source_tag = provider_source_tag()
        model_id   = provider_model_id()

        try:
            agent = self._ensure_agent()
            prompt = self._build_prompt(state)

            agent_result = await agent.invoke_async(prompt)
            text = str(agent_result)
            data = _extract_json_object(text)

            recommendation = data.get("recommendation")
            if recommendation not in ALLOWED_RECOMMENDATIONS:
                raise ValueError(f"Model returned invalid recommendation: {recommendation!r}")

            reason_codes = data.get("reason_codes") or []
            if not isinstance(reason_codes, list):
                reason_codes = [str(reason_codes)]
            reason_codes = [str(r) for r in reason_codes]

            summary     = str(data.get("summary") or "")
            rationale   = str(data.get("rationale") or "")
            next_action = str(data.get("next_action") or "")

            state["result"] = {
                "recommendation": recommendation,
                "reason_codes":   reason_codes,
                "rationale":      rationale,
                "next_action":    next_action,
                "summary":        summary,
            }
            trace_reasons = []
            if summary:
                trace_reasons.append(summary)
            trace_reasons.extend(reason_codes)
            if rationale:
                trace_reasons.append(f"Rationale: {rationale}")
            if next_action:
                trace_reasons.append(f"Next action: {next_action}")

            _trace(
                state,
                self.id,
                recommendation,
                reasons=trace_reasons,
                evidence={
                    "final_recommendation": recommendation,
                    "source":               source_tag,
                    "model_id":             model_id,
                    "rationale":            rationale,
                    "next_action":          next_action,
                    "raw_reason_codes":     reason_codes,
                },
            )
            status = Status.COMPLETED

        except Exception as exc:
            # LLM call failed — run the deterministic outcome so the run completes.
            # Stamp the trace entry so the UI shows we fell back AND which
            # provider was attempted before falling back.
            case_screening_outcome_agent(state)
            if state["trace"] and state["trace"][-1]["agent_key"] == self.id:
                state["trace"][-1].setdefault("evidence", {})
                state["trace"][-1]["evidence"]["source"]             = "deterministic_fallback"
                state["trace"][-1]["evidence"]["attempted_provider"] = source_tag
                state["trace"][-1]["evidence"]["model_id"]           = model_id
                state["trace"][-1]["evidence"]["fallback_reason"]    = str(exc)[:200]
            status = Status.COMPLETED

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return MultiAgentResult(
            status=status,
            results={
                self.id: NodeResult(
                    result=MultiAgentResult(status=status),
                    status=status,
                    execution_time=elapsed_ms,
                    execution_count=1,
                ),
            },
            execution_time=elapsed_ms,
            execution_count=1,
        )
