"""
model_provider.py — pluggable LLM provider for the outcome agent.

The 5th graph node (case screening outcome) uses an LLM to synthesise the trace
from the upstream deterministic agents into a final recommendation. To keep the
prototype portable across Origin's hybrid cloud reality, the provider is chosen
at runtime via the LLM_PROVIDER env var:

    LLM_PROVIDER=bedrock         AWS Bedrock — Claude (default for SP51 target platform)
    LLM_PROVIDER=azure           Azure AI Foundry — Claude (alternative path)
    LLM_PROVIDER=deterministic   No LLM. Use the deterministic Python outcome agent.

This file is the single seam between Strands and the cloud provider. Adding a
new provider (e.g. Anthropic direct, Vertex) means adding one branch here.
"""

import os
from typing import Any

from strands.models.anthropic import AnthropicModel
from strands.models.bedrock import BedrockModel


PROVIDER_BEDROCK       = "bedrock"
PROVIDER_AZURE_FOUNDRY = "azure"
PROVIDER_DETERMINISTIC = "deterministic"

VALID_PROVIDERS = {PROVIDER_BEDROCK, PROVIDER_AZURE_FOUNDRY, PROVIDER_DETERMINISTIC}


def get_provider() -> str:
    """Read LLM_PROVIDER once and normalise. Default = deterministic (safe for dev)."""
    raw = os.environ.get("LLM_PROVIDER", PROVIDER_DETERMINISTIC).strip().lower()
    if raw not in VALID_PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER={raw!r}. "
            f"Valid values: {sorted(VALID_PROVIDERS)}"
        )
    return raw


def get_outcome_model() -> Any:
    """
    Build the Strands model for the outcome agent based on LLM_PROVIDER.

    Returns a Strands-compatible Model instance. Caller wraps it in a Strands
    Agent. Raises ValueError if the provider is unknown or required env vars
    are missing.

    Should NOT be called when LLM_PROVIDER=deterministic — the caller picks the
    deterministic node directly in that case.
    """
    provider = get_provider()

    if provider == PROVIDER_BEDROCK:
        model_id = os.environ.get(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        region = os.environ.get("AWS_REGION", "us-east-1")
        return BedrockModel(model_id=model_id, region_name=region)

    if provider == PROVIDER_AZURE_FOUNDRY:
        endpoint   = _require_env("AZURE_AI_FOUNDRY_ENDPOINT")
        api_key    = _require_env("AZURE_AI_FOUNDRY_API_KEY")
        deployment = _require_env("AZURE_AI_FOUNDRY_DEPLOYMENT")

        # Azure AI Foundry exposes Claude via an Anthropic-compatible passthrough
        # at <resource>.services.ai.azure.com/anthropic/. The standard Anthropic
        # Python SDK speaks this protocol directly — we just override base_url.
        # The "deployment" is the name Foundry assigned to the Claude deployment.
        return AnthropicModel(
            client_args={
                "api_key":  api_key,
                "base_url": endpoint.rstrip("/") + "/",
            },
            model_id=deployment,
            max_tokens=4096,
        )

    raise ValueError(f"get_outcome_model() called with provider={provider!r}")


def provider_source_tag() -> str:
    """
    Tag stamped onto the trace evidence.source field so the UI and audit log
    show which provider produced the final recommendation.
    """
    p = get_provider()
    return {
        PROVIDER_BEDROCK:       "llm_bedrock",
        PROVIDER_AZURE_FOUNDRY: "llm_azure_foundry",
        PROVIDER_DETERMINISTIC: "deterministic",
    }[p]


def provider_model_id() -> str:
    """Human-readable model identifier for logging / UI."""
    provider = get_provider()
    if provider == PROVIDER_BEDROCK:
        return os.environ.get("BEDROCK_MODEL_ID", "claude-sonnet-4-5 (bedrock)")
    if provider == PROVIDER_AZURE_FOUNDRY:
        deployment = os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "claude")
        return f"{deployment} (azure-foundry)"
    return "deterministic"


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ValueError(
            f"Missing required env var {key} for LLM_PROVIDER=azure. "
            f"See backend/.env.azure.example for the full list."
        )
    return val
