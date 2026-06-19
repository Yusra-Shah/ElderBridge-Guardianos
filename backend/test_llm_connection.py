"""
ElderBridge GuardianOS — standalone Azure OpenAI connection test.

Loads .env from the project root, makes one test call to the Azure OpenAI
endpoint, and prints the response or a clear error message.

Usage (run from the backend/ directory):
    python test_llm_connection.py

Environment variables read from .env (project root):
  AZURE_OPENAI_API_KEY     — required: API key for the Azure OpenAI resource
  AZURE_OPENAI_ENDPOINT    — required: resource root URL, e.g.
                             https://<resource>.openai.azure.com
                             (NOT the AI Foundry /api/projects/... path)
  AZURE_OPENAI_DEPLOYMENT  — required: deployment name, e.g. gpt-5-mini
  AZURE_OPENAI_API_VERSION — optional: api-version (default 2024-12-01-preview)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env before importing llm.client
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
loaded = load_dotenv(_env_path)

# Add backend/ to sys.path so local package imports resolve when run directly
sys.path.insert(0, str(Path(__file__).parent))

from llm.client import LLMUnavailableError, call_llm  # noqa: E402


def _mask(value: str) -> str:
    if not value:
        return "NOT SET"
    if len(value) > 12:
        return value[:8] + "..." + value[-4:] + "  (set)"
    return "****  (set)"


def main() -> None:
    api_key     = os.environ.get("AZURE_OPENAI_API_KEY",     "").strip()
    endpoint    = os.environ.get("AZURE_OPENAI_ENDPOINT",    "").strip()
    deployment  = os.environ.get("AZURE_OPENAI_DEPLOYMENT",  "").strip()
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "").strip() or "2024-12-01-preview"

    full_url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
        if endpoint and deployment else "n/a"
    )

    print()
    print("ElderBridge - Azure OpenAI connection test")
    print("-" * 44)
    print(f"  .env file:    {_env_path}")
    print(f"                ({'loaded' if loaded else 'not found - using shell env'})")
    print(f"  Endpoint:     {endpoint or 'NOT SET'}")
    print(f"  Deployment:   {deployment or 'NOT SET'}")
    print(f"  API version:  {api_version}")
    print(f"  API key:      {_mask(api_key)}")
    print(f"  Request URL:  {full_url}")
    print()

    try:
        response = call_llm(
            system_prompt="You are a helpful assistant.",
            user_message="Say hello in one sentence.",
            max_tokens=2048,
        )
        print("[OK] LLM responded:")
        print(f"     {response}")
    except LLMUnavailableError as exc:
        print(f"[ERROR] LLM unavailable: {exc}")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
