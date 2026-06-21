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
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

logger = logging.getLogger("elderbridge.llm.client")


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached or used for any reason.

    Covers: missing/empty env vars, network errors, timeouts, rate limits,
    API-level errors.  Callers should catch this and fall back to rule-based
    responses rather than propagating the error to the user.
    """


class ContentFilterError(LLMUnavailableError):
    """Azure content filter blocked the request (jailbreak or content_filter).

    Callers should fall back gracefully — the input text itself is harmless
    but tripped Azure's automated filter (common with messy accessibility dumps).
    """


# ---------------------------------------------------------------------------
# Text sanitization — clean messy accessibility dumps before sending to Azure
# ---------------------------------------------------------------------------

_URL_QUERY_RE = re.compile(r'(https?://\S+?)([?#]\S*)')
_TRACKING_PARAMS_RE = re.compile(r'[?&](igsh|igshid|utm_\w+|fbclid|t|s|ref|share)=[^\s&]*', re.IGNORECASE)
_PERCENT_ENCODED_RE = re.compile(r'%[0-9A-Fa-f]{2}')
_UNICODE_ICON_RE = re.compile(r'[-\U000f0000-\U000ffffd⠀-⣿]')
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_DUPLICATE_PHRASE_RE = re.compile(r'\b(\w[\w\s]{2,30}?)\s+\1\b', re.IGNORECASE)
_MULTI_SPACE_RE = re.compile(r'[ \t]{2,}')
_MULTI_NEWLINE_RE = re.compile(r'\n{3,}')
_RAW_URL_RE = re.compile(r'https?://\S{60,}')
_SOCIAL_PROFILE_RE = re.compile(
    r'(?:facebook|instagram|twitter|linkedin|youtube|tiktok)\.com/\S*',
    re.IGNORECASE,
)
_MAP_NOISE_RE = re.compile(
    r'(leaflet|openstreetmap|map\s*data|zoom\s*in|zoom\s*out|'
    r'no\s+officials?\s+data\s+available|'
    r'keyboard_arrow_\w+|'
    r'accessibility\s*menu|'
    r'map\s*marker|'
    r'tiles\s+courtesy)',
    re.IGNORECASE,
)
_NAV_JUNK_RE = re.compile(
    r'\b(share\s*button|bookmark\s*button|more\s*options|navigate\s*up|'
    r'action_\w+|content_\w+|ic_\w+)\b',
    re.IGNORECASE,
)


def sanitize_for_llm(text: str) -> str:
    """Clean raw accessibility text before sending to Azure to avoid content filter false positives.

    Strips URL tracking params, percent-encoded noise, private-use unicode icons,
    control characters, social media profile URLs, map widget noise, leaflet/OSM
    attribution, accessibility labels, and collapses repeated duplicate phrases.
    """
    if not text:
        return text

    text = _CONTROL_CHARS_RE.sub('', text)
    text = _UNICODE_ICON_RE.sub('', text)

    text = _URL_QUERY_RE.sub(lambda m: m.group(1), text)
    text = _TRACKING_PARAMS_RE.sub('', text)
    text = _PERCENT_ENCODED_RE.sub('', text)

    text = _RAW_URL_RE.sub(lambda m: m.group()[:40], text)
    text = _SOCIAL_PROFILE_RE.sub('', text)
    text = _MAP_NOISE_RE.sub('', text)
    text = _NAV_JUNK_RE.sub('', text)

    text = _DUPLICATE_PHRASE_RE.sub(r'\1', text)

    text = _MULTI_SPACE_RE.sub(' ', text)
    text = _MULTI_NEWLINE_RE.sub('\n\n', text)

    return text.strip()


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

    user_message = sanitize_for_llm(user_message)

    try:
        from openai import BadRequestError, OpenAI

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
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            finish = response.choices[0].finish_reason
            raise LLMUnavailableError(
                f"LLM returned empty content (finish_reason={finish!r}). "
                "Increase max_completion_tokens or check the token budget."
            )
        return content
    except (LLMUnavailableError, ContentFilterError):
        raise
    except BadRequestError as exc:
        body = getattr(exc, "body", {}) or {}
        code = body.get("code", "") if isinstance(body, dict) else ""
        if "content_filter" in str(code) or "content_filter" in str(exc):
            logger.warning("Azure content filter triggered (not a real threat): %s", exc)
            raise ContentFilterError(f"Azure content filter: {exc}") from exc
        logger.error("LLM BadRequestError: %s", exc, exc_info=True)
        raise LLMUnavailableError(f"LLM call failed: {exc}") from exc
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


def call_llm_chat(messages: list[dict], max_tokens: int = 512) -> str:
    """Call Azure OpenAI with a full multi-turn messages array.

    Each dict in messages must have ``role`` ("system", "user", or "assistant")
    and ``content`` (str).  This is the standard OpenAI chat-completions format.

    Args:
        messages:   Ordered list of conversation messages.
        max_tokens: Token budget for the completion.

    Returns:
        The model's plain-text response string.

    Raises:
        LLMUnavailableError: On any failure.
    """
    api_key    = os.environ.get("AZURE_OPENAI_API_KEY",    "").strip()
    endpoint   = os.environ.get("AZURE_OPENAI_ENDPOINT",   "").strip()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT",  "").strip()

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
            f"Missing required environment variable(s): {', '.join(missing)}."
        )

    base_url = f"{endpoint.rstrip('/')}/openai/v1"

    sanitized = []
    for m in messages:
        sanitized.append({
            "role": m["role"],
            "content": sanitize_for_llm(m["content"]) if m.get("content") else "",
        })

    try:
        from openai import BadRequestError, OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=deployment,
            messages=sanitized,
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            finish = response.choices[0].finish_reason
            raise LLMUnavailableError(
                f"LLM returned empty content (finish_reason={finish!r})."
            )
        return content
    except (LLMUnavailableError, ContentFilterError):
        raise
    except BadRequestError as exc:
        body = getattr(exc, "body", {}) or {}
        code = body.get("code", "") if isinstance(body, dict) else ""
        if "content_filter" in str(code) or "content_filter" in str(exc):
            logger.warning("Azure content filter on chat (not a real threat): %s", exc)
            raise ContentFilterError(f"Azure content filter: {exc}") from exc
        logger.error("LLM chat BadRequestError: %s", exc, exc_info=True)
        raise LLMUnavailableError(f"LLM chat call failed: {exc}") from exc
    except Exception as exc:
        logger.error("LLM chat call failed: %s", exc, exc_info=True)
        raise LLMUnavailableError(f"LLM chat call failed: {exc}") from exc
