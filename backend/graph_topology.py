"""
graph_topology.py — the Strands graph map.

This is the file that turns "5 functions in a list" into a real directed graph
with conditional edges. Skip logic lives in the EDGE CONDITIONS, not inside the
agents. If triage decides RETURN_TO_ONSHORE_EXCLUDED, the graph jumps straight to the
outcome node — precheck / groundrule / sop_context literally do not run.

Topology:

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

The outcome node is unconditionally reached from any of the four upstream nodes,
because all paths terminate there.

Provider selection for the outcome node is read at import time from LLM_PROVIDER
(see model_provider.py for the env var matrix). Defaults to `deterministic` so
local dev works with no cloud creds.
"""

from strands.multiagent.graph import GraphBuilder

from agents import (
    case_intake_triage_agent,
    precheck_agent,
    groundrule_agent,
    sop_context_agent,
    case_screening_outcome_agent,
)
from graph_nodes import DeterministicNode, LLMOutcomeNode
from model_provider import PROVIDER_DETERMINISTIC, get_provider


def build_screening_graph(state: dict):
    """
    Build a fresh Strands Graph for one screening run.

    Edge conditions close over `state` so they can read the flags that the
    agents set as they run (triage_excluded, precheck_blocked, groundrule_unworkable).
    Strands evaluates these conditions AFTER each node completes.
    """
    triage     = DeterministicNode("case_intake_triage", case_intake_triage_agent)
    precheck   = DeterministicNode("precheck",           precheck_agent)
    groundrule = DeterministicNode("groundrule",         groundrule_agent)
    sop        = DeterministicNode("sop_context",        sop_context_agent)

    # Final node: real Strands+LLM agent (Bedrock or Azure AI Foundry) when
    # LLM_PROVIDER is set to a provider, else the deterministic if/elif chain.
    # Same graph shape either way.
    if get_provider() == PROVIDER_DETERMINISTIC:
        outcome = DeterministicNode("screening_outcome", case_screening_outcome_agent)
    else:
        outcome = LLMOutcomeNode("screening_outcome")

    ctx = state["context"]

    def triage_ok(_):       return not ctx.get("triage_excluded")
    def triage_excluded(_): return bool(ctx.get("triage_excluded"))

    def precheck_ok(_):      return not ctx.get("precheck_blocked")
    def precheck_blocked(_): return bool(ctx.get("precheck_blocked"))

    def ground_ok(_):         return not ctx.get("groundrule_unworkable")
    def ground_unworkable(_): return bool(ctx.get("groundrule_unworkable"))

    b = GraphBuilder()
    b.add_node(triage,     "case_intake_triage")
    b.add_node(precheck,   "precheck")
    b.add_node(groundrule, "groundrule")
    b.add_node(sop,        "sop_context")
    b.add_node(outcome,    "screening_outcome")

    b.set_entry_point("case_intake_triage")

    b.add_edge("case_intake_triage", "precheck",          condition=triage_ok)
    b.add_edge("case_intake_triage", "screening_outcome", condition=triage_excluded)

    b.add_edge("precheck", "groundrule",         condition=precheck_ok)
    b.add_edge("precheck", "screening_outcome",  condition=precheck_blocked)

    b.add_edge("groundrule", "sop_context",        condition=ground_ok)
    b.add_edge("groundrule", "screening_outcome",  condition=ground_unworkable)

    b.add_edge("sop_context", "screening_outcome")

    b.set_max_node_executions(10)  # safety bound — graph is acyclic, 5 nodes max
    return b.build()
