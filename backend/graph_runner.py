"""
graph_runner.py — boots a real Strands Graph and forwards its events.

The runner does three things:
  1. Build the graph (graph_topology.build_screening_graph).
  2. Call graph.stream_async(...) — this is the REAL Strands event stream.
  3. Translate each Strands event into the WebSocket event shape the frontend
     already understands (agent_status running / done, final_result).

We no longer drive a for-loop over agents — Strands does that, respecting the
edge conditions defined in graph_topology.py.
"""

import asyncio

from events import agent_running_event, agent_done_event, final_result_event
from graph_topology import build_screening_graph


async def run_screening_graph(case: dict, send_event=None) -> dict:
    """
    Run a billing exception case through the Strands graph.

    case        — dict with case_id, account_number, esiid, exception_type, ...
    send_event  — async callable(event_dict). None for REST; set for WebSocket.

    Returns the final state + trace.
    """
    state = {
        "case":    case,
        "context": {},
        "trace":   [],
        "result":  None,
    }
    case_id = case["case_id"]

    graph = build_screening_graph(state)

    async for event in graph.stream_async(
        task="screen_case",
        invocation_state={"state": state},
    ):
        kind = event.get("type")

        if kind == "multiagent_node_start":
            node_id = event["node_id"]
            if send_event:
                await send_event(agent_running_event(case_id, node_id))
            # UI pacing — gives the frontend ~0.6s to show "running" before "done".
            # Strands runs the node concurrently, so this does not slow the node itself.
            await asyncio.sleep(0.6)

        elif kind == "multiagent_node_stop":
            node_id = event["node_id"]
            latest = state["trace"][-1] if state["trace"] else {}
            if send_event:
                await send_event(agent_done_event(
                    case_id=case_id,
                    agent_key=node_id,
                    decision=latest.get("decision", ""),
                    reasons=latest.get("reasons", []),
                    rule_hits=latest.get("rule_hits", []),
                    evidence=latest.get("evidence", {}),
                ))

    if send_event:
        await send_event(final_result_event(
            case_id=case_id,
            result=state["result"],
            trace=state["trace"],
        ))

    return {
        "case":          state["case"],
        "result":        state["result"],
        "trace":         state["trace"],
        "graph_pattern": "Strands GraphBuilder with conditional edges (real graph topology)",
    }