"""
ElderBridge GuardianOS — Azure AI Foundry LLM client wrapper.

Uses the openai Python package pointed at an Azure AI Foundry project endpoint
via the OpenAI-compatible /openai/v1 path.

Model note:
  gpt-5-mini (and other reasoning models like o1/o3) require
  max_completion_tokens instead of max_tokens, and need a larger budget
  because internal reasoning tokens are charged against the same limit.

Security note (SECURITY_MODEL.md §7):
  All credentials are read from environment variables at call time.
  NEVER hardcode secrets here or anywhere else in the codebase.

Required environment variables (set in .env or deployment environment):
  AZURE_OPENAI_API_KEY    — API key for the Azure AI Foundry resource
  AZURE_OPENAI_ENDPOINT   — Foundry project URL, e.g.
                            https://<resource>.services.ai.azure.com/api/projects/<project>
  AZURE_OPENAI_DEPLOYMENT — Model name, e.g. gpt-5-mini
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

logger = logging.getLogger("elderbridge.llm.client")


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached or used for any reason.

    Covers: missing/empty env vars, network errors, timeouts, rate limits,
    API-level errors.  Callers should catch this and fall back to rule-based
    responses rather than propagating the error to the user.
    """


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    deployment_name: str | None = None,
) -> str:
    """
    Call the Azure OpenAI chat completions endpoint and return the response text.

    Args:
        system_prompt:   Content for the ``system`` message.
        user_message:    Content for the ``user`` message.
        max_tokens:      Token budget for the completion (default 4096).
                         Passed as ``max_completion_tokens`` in the API call.
        deployment_name: Azure deployment to use.  If None, reads from
                         AZURE_OPENAI_DEPLOYMENT env var.

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
    deployment = (deployment_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")).strip()

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

    # Azure AI Foundry project endpoint uses /openai/v1 path.
    # The model name is passed in the create() call, not in the URL.
    base_url = f"{endpoint.rstrip('/')}/openai/v1"

    try:
        from openai import OpenAI  # deferred import so module loads without package installed

        logger.debug(
            "LLM backend: Azure AI Foundry base_url=%s model=%s",
            base_url, deployment,
        )

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
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


def call_llm_race(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    """Race multiple Azure deployments and return the first successful response.

    Submits requests to gpt-5.4-nano and gpt-5.2 in parallel.  Returns the
    first non-empty result.  If both fail or timeout after 45s, falls back to
    the default deployment (gpt-5-mini via AZURE_OPENAI_DEPLOYMENT env var).

    Raises:
        LLMUnavailableError: If all deployments including the fallback fail.
    """
    deployments = ["gpt-5.4-nano", "gpt-5.2"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                call_llm, system_prompt, user_message, max_tokens, dep
            ): dep
            for dep in deployments
        }
        try:
            for future in as_completed(futures, timeout=45):
                dep = futures[future]
                try:
                    result = future.result()
                    if result and result.strip():
                        print(f"[RACE] Winner: {dep}")
                        return result
                except Exception as e:
                    print(f"[RACE] {dep} failed: {e}")
        except FuturesTimeoutError:
            print("[RACE] Both models timed out, falling back")

    return call_llm(system_prompt, user_message, max_tokens)
