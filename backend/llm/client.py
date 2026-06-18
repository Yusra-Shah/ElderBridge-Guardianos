"""
ElderBridge GuardianOS — Azure OpenAI LLM client wrapper.

Uses the openai Python package pointed at an Azure OpenAI endpoint via the
chat completions API.  Supports both classic Azure OpenAI and Azure AI Foundry
resources (both expose the same /openai/deployments/... path).

Model note:
  gpt-5-mini (and other reasoning models like o1/o3) require
  max_completion_tokens instead of max_tokens, and need a larger budget
  because internal reasoning tokens are charged against the same limit.
  The default here is 2048 to ensure reasoning + output both fit.

Security note (SECURITY_MODEL.md §7):
  All credentials are read from environment variables at call time.
  NEVER hardcode secrets here or anywhere else in the codebase.

Required environment variables (set in .env or deployment environment):
  AZURE_OPENAI_API_KEY    — API key for the Azure OpenAI resource
  AZURE_OPENAI_ENDPOINT   — Resource root URL, e.g.
                            https://<resource>.openai.azure.com
                            (NOT the AI Foundry /api/projects/... path)
  AZURE_OPENAI_DEPLOYMENT — Deployment name, e.g. gpt-5-mini

Optional:
  AZURE_OPENAI_API_VERSION — api-version query param
                             (default: 2024-12-01-preview)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("elderbridge.llm.client")


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached or used for any reason.

    Covers: missing/empty env vars, network errors, timeouts, rate limits,
    API-level errors.  Callers should catch this and fall back to rule-based
    responses rather than propagating the error to the user.
    """


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 2048) -> str:
    """
    Call the Azure OpenAI chat completions endpoint and return the response text.

    Args:
        system_prompt: Content for the ``system`` message.
        user_message:  Content for the ``user`` message.
        max_tokens:    Token budget for the completion (default 512).
                       Passed as ``max_completion_tokens`` in the API call.
                       NOTE: reasoning models (gpt-5-mini, o1, o3, …) consume
                       tokens internally for chain-of-thought before producing
                       any visible output.  If you get empty responses or
                       finish_reason="length", raise this value to 1024–2048.

    Returns:
        The model's plain-text response string.

    Raises:
        LLMUnavailableError: For any failure — missing env vars, network error,
                             timeout, rate limit, or API-level error.
                             Callers should catch this and fall back gracefully.
    """
    # Read all credentials at call time so tests can patch os.environ freely
    api_key    = os.environ.get("AZURE_OPENAI_API_KEY",    "").strip()
    endpoint   = os.environ.get("AZURE_OPENAI_ENDPOINT",   "").strip()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
    api_version = (
        os.environ.get("AZURE_OPENAI_API_VERSION", "").strip()
        or "2024-12-01-preview"
    )

    missing = [
        name for name, val in (
            ("AZURE_OPENAI_API_KEY",    api_key),
            ("AZURE_OPENAI_ENDPOINT",   endpoint),
            ("AZURE_OPENAI_DEPLOYMENT", deployment),
        )
        if not val
    ]
    if missing:
        raise LLMUnavailableError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in your .env file. Never hardcode secrets in source code."
        )

    # Construct the per-deployment base URL that the OpenAI client will use.
    # The client appends /chat/completions to produce the final request URL:
    #   {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=...
    base_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"

    try:
        from openai import OpenAI  # deferred import so module loads without package installed

        logger.debug(
            "LLM backend: Azure OpenAI base_url=%s api_version=%s",
            base_url, api_version,
        )

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_query={"api-version": api_version},
        )
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            # Reasoning models (gpt-5-mini, o1, o3, …) require max_completion_tokens.
            # Non-reasoning models also accept it, so this is safe for all deployments.
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            # Reasoning models (gpt-5-mini, o1, o3) can return empty content
            # when max_completion_tokens is too small to fit both chain-of-thought
            # and visible output.  Treat as unavailable so callers fall back.
            finish = response.choices[0].finish_reason
            raise LLMUnavailableError(
                f"LLM returned empty content (finish_reason={finish!r}). "
                "Increase max_completion_tokens or check the token budget."
            )
        return content
    except Exception as exc:
        logger.error("LLM call failed: %s", exc, exc_info=True)
        raise LLMUnavailableError(f"LLM call failed: {exc}") from exc
