"""
ElderBridge GuardianOS — Thin Anthropic LLM client wrapper.

Security note (SECURITY_MODEL.md §7):
  API key is read from os.environ["ANTHROPIC_API_KEY"] at call time.
  NEVER hardcode secrets here or anywhere else in the codebase.

Environment variables (set in .env or deployment environment, never in code):
  ANTHROPIC_API_KEY — Anthropic API key required for LLM calls
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("elderbridge.llm.client")

# Model identifier — matches the deployment model for this project
MODEL = "claude-sonnet-4-6"


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached or used for any reason.

    Covers: missing/empty API key, network errors, timeouts, rate limits,
    API-level errors.  Callers should catch this and fall back to rule-based
    responses rather than propagating the error to the user.
    """


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 512) -> str:
    """
    Call the Anthropic Messages API and return the text response.

    Args:
        system_prompt: System-level instructions sent as the ``system`` field.
        user_message:  User turn content.
        max_tokens:    Maximum tokens in the model completion (default 512).

    Returns:
        The model's plain-text response string (first content block).

    Raises:
        LLMUnavailableError: For any failure — missing/empty API key, network
                             error, timeout, rate limit, or API-level error.
                             Callers should catch this and fall back gracefully.
    """
    # Read key at call time so tests can patch os.environ without module-level caching
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise LLMUnavailableError(
            "ANTHROPIC_API_KEY is not set or empty. "
            "Set it in your deployment environment (see .env.example). "
            "Never hardcode secrets in source code."
        )

    try:
        import anthropic  # deferred import so module loads without package installed

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except Exception as exc:
        logger.error("LLM call failed: %s", exc, exc_info=True)
        raise LLMUnavailableError(f"Anthropic API call failed: {exc}") from exc
