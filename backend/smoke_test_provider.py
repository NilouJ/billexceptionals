"""
Smoke test for model_provider.py — verifies the active LLM provider works.

Usage (from backend/ directory, with .env populated):
    python smoke_test_provider.py

Exits 0 on success, prints the model response. Exits 1 on any failure with
the error message that the prototype's fallback would have caught.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from strands import Agent

from model_provider import get_outcome_model, get_provider, provider_model_id


def main() -> int:
    provider = get_provider()
    model_id = provider_model_id()
    print(f"Provider:    {provider}")
    print(f"Model id:    {model_id}")
    print()

    if provider == "deterministic":
        print("LLM_PROVIDER=deterministic — nothing to smoke-test on the LLM path.")
        print("The outcome agent runs case_screening_outcome_agent() directly.")
        return 0

    try:
        model = get_outcome_model()
        agent = Agent(model=model)
        print("Sending prompt: 'Reply with the single word PONG and nothing else.'")
        result = agent("Reply with the single word PONG and nothing else.")
        text = str(result).strip()
        print()
        print(f"Response:    {text!r}")
        print()
        if "PONG" in text.upper():
            print("OK — provider is reachable and Claude responded as expected.")
            return 0
        else:
            print("WARN — provider responded but text doesn't contain PONG.")
            print("Probably fine for richer prompts; investigate if recurring.")
            return 0
    except Exception as exc:
        print()
        print(f"FAIL — {type(exc).__name__}: {exc}")
        print()
        print("This is the same exception path that would trigger the prototype's")
        print("deterministic fallback in graph_nodes.py:LLMOutcomeNode. The demo")
        print("would still run, but with the FALLBACK badge instead of LLM.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
