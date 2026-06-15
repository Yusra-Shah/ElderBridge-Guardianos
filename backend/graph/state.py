"""
ElderBridge GuardianOS — Pipeline State definition.

PipelineState is the single shared data structure that flows through every
node in the graph, exactly as in LangGraph's StateGraph pattern.

Design principles:
  - TypedDict (not Pydantic) keeps the state as a plain dict at runtime,
    which is idiomatic for LangGraph and avoids deep-copy overhead.
  - total=False means all keys are optional at the TypedDict level; actual
    required presence is enforced at construction time via make_initial_state().
  - Nodes read keys they need and return a dict spread to write their outputs:
      return {**state, "routed_agents": [...]}
  - This mirrors LangGraph's reducer / partial-update pattern so swapping in
    real LangGraph later is a one-file change in build_graph.py.

LangGraph equivalence note:
  In real LangGraph, `state_schema` is the TypedDict class itself; nodes may
  return partial dicts and LangGraph merges them.  Our CompiledGraph does the
  same merge via the dict spread in each node.
"""
from __future__ import annotations

from typing import TypedDict

from schemas.decision_schema import AgentResponse, EvidenceItem, FinalDecision, RiskLevel
from schemas.event_schema import IncomingEvent


class PipelineState(TypedDict, total=False):
    """
    Shared state flowing through every graph node.

    Fields are written by the node that owns them and read by downstream nodes.
    All fields are declared optional (total=False) because nodes receive the
    current state and return an extended copy — never a fresh one.

    Ownership map:
      event               → injected by run_graph(), never mutated
      routed_agents       → written by node_router
      agent_responses     → accumulated by each specialist node
      evidence_items      → accumulated by node_research
      draft_response      → written by node_baseline
      risk_flag           → written by node_baseline
      next_steps          → written by node_baseline
      last_critic_response→ written by node_critic (for testing + logging)
      final_decision      → written by node_guardrail (terminal output)
    """

    # ── Input (always present after make_initial_state) ───────────────────
    event: IncomingEvent

    # ── Router output ─────────────────────────────────────────────────────
    routed_agents: list[str]           # e.g. ["FormAgent", "BenefitsAgent"]

    # ── Specialist accumulator ────────────────────────────────────────────
    agent_responses: list[AgentResponse]
    evidence_items: list[EvidenceItem]  # collected from ResearchAgent only

    # ── Baseline output (rule-based risk assessment) ──────────────────────
    draft_response: str                 # initial response text from rules
    risk_flag: RiskLevel                # NONE … CONTACT_TRUSTED_PERSON
    next_steps: list[str]

    # ── Critic output (for logging + test introspection) ──────────────────
    last_critic_response: AgentResponse | None

    # ── Terminal output (written by guardrail, consumed by run_graph) ─────
    final_decision: FinalDecision | None


def make_initial_state(event: IncomingEvent) -> PipelineState:
    """
    Create a fully initialised PipelineState for a new request.

    Every key is given a safe default so nodes can use .get() freely without
    KeyError, and dict spread ({**state, "key": val}) stays consistent.
    """
    return {  # type: ignore[return-value]  — TypedDict created as a plain dict
        "event": event,
        "routed_agents": [],
        "agent_responses": [],
        "evidence_items": [],
        "draft_response": "",
        "risk_flag": RiskLevel.NONE,
        "next_steps": [],
        "last_critic_response": None,
        "final_decision": None,
    }
