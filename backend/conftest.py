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
# BenefitsAgent now calls call_llm().  Without a real ANTHROPIC_API_KEY the
# function raises RuntimeError, which would break every test that runs
# run_graph() or run_pipeline() through the full pipeline.
#
# This autouse fixture stubs call_llm with a safe, hedged response so that
# all existing graph and orchestrator tests stay offline.
#
# Tests in test_benefits_agent_llm.py that use @patch("agents.benefits_agent.call_llm")
# have their patch applied after this fixture starts, so the decorator's mock
# takes precedence inside those tests — this fixture does not interfere.
# ---------------------------------------------------------------------------

_OFFLINE_LLM_RESPONSE = (
    "You may qualify based on the information provided for this benefit program. "
    "Please verify your eligibility directly with the official agency or a trusted caseworker."
)


@pytest.fixture(autouse=True)
def _stub_llm_offline():
    """Patch call_llm for every test unless the test applies its own @patch."""
    with patch(
        "agents.benefits_agent.call_llm",
        return_value=_OFFLINE_LLM_RESPONSE,
    ):
        yield
