"""
Full-graph smoke test — runs one sample case through the Strands screening
graph end-to-end with the configured LLM_PROVIDER.

Usage (from backend/ directory, with .env populated):
    python smoke_test_graph.py [case_index]

case_index defaults to 0 (CASE-001 — the clean WORKABLE case). Pass 1 for the
Ombudsman EXCLUDE case, 2 for the pinned-hold EXCLUDE, etc.
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from graph_runner import run_screening_graph


def main(case_index: int) -> int:
    sample_path = Path(__file__).parent / "data" / "sample_cases.json"
    cases = json.loads(sample_path.read_text())
    if case_index >= len(cases):
        print(f"FAIL — case_index {case_index} out of range (have {len(cases)} cases)")
        return 1

    case = cases[case_index]
    print(f"Running case: {case['case_id']} — {case['description']}")
    print()

    final = asyncio.run(run_screening_graph(case))

    result = final.get("result") or {}
    trace  = final.get("trace") or []

    print("Trace:")
    for i, t in enumerate(trace, 1):
        rule_ids = [h["rule_id"] for h in t.get("rule_hits", [])]
        chips = f" {rule_ids}" if rule_ids else ""
        print(f"  {i}. {t['agent_key']:25s} -> {t['decision']:25s}{chips}")
    print()

    print("Final result:")
    print(f"  recommendation: {result.get('recommendation')}")
    print(f"  reason_codes:")
    for rc in result.get("reason_codes", []):
        print(f"    - {rc}")
    if result.get("rationale"):
        print(f"  rationale:    {result['rationale']}")
    if result.get("next_action"):
        print(f"  next_action:  {result['next_action']}")
    print()

    # Check the last trace entry's evidence.source to confirm provider path.
    last_evidence = trace[-1].get("evidence", {}) if trace else {}
    source = last_evidence.get("source", "?")
    model_id = last_evidence.get("model_id", "?")
    print(f"Outcome agent source:  {source}")
    print(f"Outcome agent model:   {model_id}")
    if source == "deterministic_fallback":
        print(f"Fallback reason:       {last_evidence.get('fallback_reason')}")
        print("FAIL — LLM path errored; fix model_provider.py before demo.")
        return 1

    print()
    print("OK — full screening graph ran end-to-end through the configured provider.")
    return 0


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    sys.exit(main(idx))
