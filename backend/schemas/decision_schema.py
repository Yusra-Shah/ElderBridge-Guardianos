from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Decision levels from the ensemble engine (AI_AGENTS.md §17)."""
    SILENT = "silent"
    SOFT_HELP = "soft_help"
    CAUTION = "caution"
    VERIFY_FIRST = "verify_first"
    STOP_AND_VERIFY = "stop_and_verify"
    CONTACT_TRUSTED_PERSON = "contact_trusted_person"


class AgentResponse(BaseModel):
    """Structured output returned by every specialist agent."""

    agent_name: str = Field(
        ...,
        description="Canonical name of the agent that produced this response.",
    )
    output_text: str = Field(
        ...,
        description=(
            "Human-readable explanation or assessment from this agent. "
            "Must use hedged language: 'may', 'could', 'I could not verify' — "
            "never 'you qualify' or 'this is definitely safe/a scam'."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent confidence score in [0.0, 1.0]. Internal use only; never shown raw to the user.",
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source identifiers or citation labels used to produce this output (e.g. RAG doc IDs, official URLs).",
    )
    requires_human_review: bool = Field(
        ...,
        description=(
            "True when the agent determines a human (caregiver, case worker, "
            "official agency) must make the final decision."
        ),
    )


class FinalDecision(BaseModel):
    """Aggregated output returned to the Android client after ensemble decisioning."""

    response_text: str = Field(
        ...,
        description=(
            "Plain-language explanation shown in the floating overlay and/or "
            "spoken via voice. Must be calm, short, and free of technical jargon."
        ),
    )
    risk_flag: RiskLevel = Field(
        ...,
        description="Risk level determined by the ensemble engine (AI_AGENTS.md §17).",
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="Ordered list of safe, concrete actions the user should take next.",
    )
    source_citations: List[str] = Field(
        default_factory=list,
        description="Official sources consulted to produce this decision. Empty if no external source was used.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response_text": (
                    "Please pause. This message asks for private information "
                    "and I could not verify it from an official source."
                ),
                "risk_flag": "stop_and_verify",
                "next_steps": [
                    "Do not enter any personal information yet.",
                    "Call the official helpline to check if this program is real.",
                    "Ask a trusted family member or caregiver to review with you.",
                ],
                "source_citations": [],
            }
        }
    }
