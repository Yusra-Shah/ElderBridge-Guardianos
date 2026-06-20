"""
Pytest configuration — ensures the backend/ directory is on sys.path so that
`import orchestrator`, `import schemas`, `import agents` all resolve when
running `pytest` from any working directory.
"""
import os
import sys
from unittest.mock import patch

import pytest

# Insert backend/ at the front of the path so all module imports use the
# local source tree rather than any installed package.
sys.path.insert(0, os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Offline LLM stub — applied to every test automatically
# ---------------------------------------------------------------------------
# BenefitsAgent and FormAgent both call call_llm().  Without real Azure OpenAI
# credentials the function raises LLMUnavailableError, which would break every
# test that runs run_graph() or run_pipeline() through the full pipeline.
#
# This autouse fixture stubs both agents' call_llm imports with safe, hedged
# responses so all graph and orchestrator tests stay fully offline.
#
# Tests that use @patch("agents.benefits_agent.call_llm") or
# @patch("agents.form_agent.call_llm") have their decorator applied after
# this fixture starts, so those patches take precedence — no interference.
# ---------------------------------------------------------------------------

_OFFLINE_LLM_RESPONSE = (
    "You may qualify based on the information provided for this benefit program. "
    "Please verify your eligibility directly with the official agency or a trusted caseworker."
)

_OFFLINE_FORM_RESPONSE = (
    "This form is asking for standard personal information needed to process "
    "your application. Each field should be filled in with your own details. "
    "If you are unsure about any field, ask a trusted person to help you."
)

_OFFLINE_CHAT_RESPONSE = (
    "Here is the answer to your question. "
    "Please ask a trusted person if you need more help."
)


@pytest.fixture(autouse=True)
def _stub_llm_offline():
    """Patch LLM calls in all agents for offline testing."""
    from middleware.security_middleware import _rate_counters
    _rate_counters.clear()
    with patch("agents.benefits_agent.call_llm", return_value=_OFFLINE_LLM_RESPONSE), \
         patch("agents.benefits_agent.call_llm_race", return_value=_OFFLINE_LLM_RESPONSE), \
         patch("agents.form_agent.call_llm", return_value=_OFFLINE_FORM_RESPONSE), \
         patch("agents.form_agent.call_llm_race", return_value=_OFFLINE_FORM_RESPONSE), \
         patch("agents.chat_handler.call_llm", return_value=_OFFLINE_CHAT_RESPONSE), \
         patch("agents.chat_handler.call_llm_chat", return_value=_OFFLINE_CHAT_RESPONSE):
        yield
