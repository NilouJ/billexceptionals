"""
chat.py — the Origin Bill Exceptions Assistant chat agent.

A second Strands Agent (reusing the same provider as the outcome agent) that
the analyst can talk to about the active case. Information-only: it never
mutates state, never takes actions; it answers questions using the case
state + trace + case-pack already produced by the screening graph.

Per-case conversation memory lives in this module (in-process). Resets when
the user selects a different case. Not persistent — for a hackathon this is
the right scope; production would back this with DynamoDB or Cosmos DB.

Streaming via Strands' stream_async — token chunks forwarded to the WebSocket.
On any error (no creds, throttle, bad model id) the WebSocket gets a single
error event and the assistant goes quiet for that turn; the chat doesn't
crash the screening flow.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Awaitable, Callable

from strands import Agent

from model_provider import get_outcome_model, get_provider, provider_model_id, PROVIDER_DETERMINISTIC


CHAT_SYSTEM_PROMPT = """You are the Origin Bill Exceptions Assistant — an information-only
co-pilot for a billing analyst working a single exception case.

Your role:
  - Answer questions about THIS case (the JSON state below).
  - Explain rule_ids (R01-xx triage, R02-xx pre-check, R03-xx ground-rule,
    R04-xx SOP context) in plain English when asked.
  - Walk through the screening trace step-by-step if the analyst is unsure
    why the case landed where it did.
  - Suggest what an analyst would typically do next, anchored to the SOP
    reference in the case-pack.
  - Cite specific data: account fields, meter reads, agreement terms.

Strict limits:
  - You DO NOT take actions. You don't override decisions, mark cases
    approved, or trigger workflows. If the analyst asks you to do that,
    tell them to use the action buttons in the UI.
  - You DO NOT invent rules or data. If something isn't in the state
    below, say "I don't have that information in this case" — never
    fabricate.
  - You DO NOT speculate on customer intent, fraud, or legal exposure.
    Stick to what the data and rules say.
  - Keep responses tight: 2-5 sentences for most questions. Use bullet
    points when listing rule hits or actions.

When asked "why was this excluded?" walk the analyst through the trace:
  1. Name the agent that decided to return-to-onshore.
  2. List the rule_ids that fired with their reasons.
  3. Point at the underlying data that triggered them.
  4. Suggest the next step (usually the case_pack.recommended_actions).
"""


# Per-case_id conversation history. Reset by call to reset_for_case().
# Structure: { case_id: [ {"role":"user"|"assistant", "content":"..."} ] }
_history: dict[str, list[dict]] = {}

# Per-case_id Strands Agent instance (cached so system prompt + provider model
# only build once per case session). Released on reset.
_agents: dict[str, Agent] = {}


def _build_agent_for(case_id: str) -> Agent:
    if case_id in _agents:
        return _agents[case_id]
    model = get_outcome_model()
    _agents[case_id] = Agent(model=model, system_prompt=CHAT_SYSTEM_PROMPT)
    return _agents[case_id]


def reset_for_case(case_id: str) -> None:
    """Clear the conversation history and agent for a case (call on new screening run)."""
    _history.pop(case_id, None)
    _agents.pop(case_id, None)


def starter_questions(case_pack: dict) -> list[str]:
    """
    Return 3 starter questions tailored to the case outcome. Sized for
    chat-panel chips — short, action-oriented.
    """
    rec = (case_pack or {}).get("recommendation", "")
    scenario = (case_pack or {}).get("scenario", "")

    if rec.startswith("RETURN_TO_ONSHORE"):
        return [
            "Why was this case returned to onshore?",
            "Which specific rules fired and what data triggered them?",
            "What does the onshore team need to do next?",
        ]
    if rec == "WORKABLE":
        return [
            f"Walk me through scenario {scenario or 'this case'}",
            "What are the recommended next actions?",
            "Show me the agreement and meter details",
        ]
    return [
        "Explain this case to me",
        "Which rules were checked?",
        "What's the recommended next action?",
    ]


def _compact_state_for_prompt(state: dict) -> dict:
    """
    Build a compact JSON document for the LLM. Works with either the full
    backend state (case + context + trace + result) or the frontend snapshot
    (case + trace + result) — the case-pack inside result carries the data
    the assistant needs.
    """
    result    = state.get("result") or {}
    case_pack = result.get("case_pack") or {}
    return {
        "case": state.get("case"),
        "result_summary": {
            "recommendation": result.get("recommendation"),
            "summary":        result.get("summary"),
            "rationale":      result.get("rationale"),
            "next_action":    result.get("next_action"),
            "reason_codes":   result.get("reason_codes"),
        },
        "case_pack": case_pack,
        "trace": [
            {
                "agent":     t.get("agent_key"),
                "decision":  t.get("decision"),
                "rule_hits": t.get("rule_hits"),
                "reasons":   t.get("reasons"),
                "evidence":  t.get("evidence"),
            }
            for t in (state.get("trace") or [])
        ],
    }


async def answer(
    case_id: str,
    user_message: str,
    state_snapshot: dict,
    send_chunk: Callable[[str], Awaitable[None]] | None = None,
) -> dict:
    """
    Respond to one analyst turn. Streams token chunks via `send_chunk` if
    provided, returns the full text plus latency.

    Returns: {"text": str, "elapsed_ms": int, "source": str, "model_id": str}
    """
    started = time.monotonic()

    if get_provider() == PROVIDER_DETERMINISTIC:
        text = (
            "The chat assistant requires an LLM provider (LLM_PROVIDER=bedrock "
            "or LLM_PROVIDER=azure). It's currently set to deterministic, so "
            "I can't reason about this case. See docs/02-provider-config.md."
        )
        if send_chunk:
            await send_chunk(text)
        return {"text": text, "elapsed_ms": 0, "source": "deterministic", "model_id": "deterministic"}

    history = _history.setdefault(case_id, [])
    agent   = _build_agent_for(case_id)

    # First user turn for this case: prefix the state document so the agent
    # has the full case context to reason against.
    if not history:
        state_doc = json.dumps(_compact_state_for_prompt(state_snapshot), indent=2, default=str)
        prompt = (
            f"Case state for the conversation (this is the only case you can answer about):\n"
            f"```json\n{state_doc}\n```\n\n"
            f"Analyst question: {user_message}"
        )
    else:
        prompt = user_message

    # Strands' Agent supports stream_async — token chunks via events of type
    # "text_delta" / "content_block_delta" depending on provider. We forward
    # the text content directly.
    text_parts: list[str] = []
    try:
        async for event in agent.stream_async(prompt):
            chunk = _extract_text_chunk(event)
            if chunk:
                text_parts.append(chunk)
                if send_chunk:
                    await send_chunk(chunk)
        text = "".join(text_parts).strip()
    except Exception as exc:
        text = f"Sorry — the assistant hit an error: {type(exc).__name__}: {exc}"
        if send_chunk:
            await send_chunk(text)

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": text})

    return {
        "text":       text,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "source":     "llm_" + get_provider(),
        "model_id":   provider_model_id(),
    }


def _extract_text_chunk(event) -> str:
    """
    Strands' stream_async event shapes differ slightly between providers.
    Try several known fields, fall back to "".
    """
    if isinstance(event, dict):
        # Anthropic-style text deltas
        if "data" in event and isinstance(event["data"], str):
            return event["data"]
        if "content" in event and isinstance(event["content"], str):
            return event["content"]
        delta = event.get("delta")
        if isinstance(delta, dict):
            txt = delta.get("text") or delta.get("content")
            if isinstance(txt, str):
                return txt
        msg = event.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                return "".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                )
            if isinstance(content, str):
                return content
    return ""
