"""
ElderBridge GuardianOS — Pipeline graph construction and execution.

Implements a LangGraph-compatible state machine using plain Python.

Why not real LangGraph?
  LangGraph 1.x installs 16 packages including langsmith (default telemetry),
  websockets, and zstandard.  For an offline-first demo that must run without
  network surprises, the dependency footprint adds unnecessary friction.
  VIBE_CODING_PROMPT.md explicitly allows "clean orchestrator if LangGraph is
  unavailable."  This module mirrors LangGraph's public API exactly so the
  swap is a one-file change when/if the project graduates to production.

LangGraph API equivalence:
  Our class          → LangGraph equivalent
  ─────────────────────────────────────────
  PipelineGraph      → StateGraph
  .add_node()        → .add_node()
  .set_entry_point() → .set_entry_point()
  .set_finish_point()→ .set_finish_point() (our extension)
  .add_edge()        → .add_edge()
  .add_conditional_edges() → .add_conditional_edges()
  .compile()         → .compile()
  CompiledGraph      → CompiledStateGraph
  .invoke()          → .invoke()

To swap in real LangGraph, replace the PipelineGraph / CompiledGraph classes
with imports from langgraph.graph and keep all node functions and the
build_pipeline_graph() body unchanged.

Graph topology:
  START
    │
  baseline  ← rule-based risk assessment
    │
  router    ← decides which specialist agents to invoke
    │
  [conditional fan-out based on routed_agents]
    ├── benefits  (if routed)
    ├── form      (if routed)
    └── research  (if routed)
    │
  critic    ← reviews all specialist outputs for overclaiming
    │
  guardrail ← final safety veto
    │
  END

Each node is logged as it executes, providing "visible problem solving"
for demo presentations.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from graph.nodes import (
    node_baseline,
    node_benefits,
    node_critic,
    node_form,
    node_guardrail,
    node_research,
    node_router,
)
from graph.state import PipelineState, make_initial_state
from schemas.decision_schema import FinalDecision
from schemas.event_schema import IncomingEvent

logger = logging.getLogger("elderbridge.graph")

# ---------------------------------------------------------------------------
# LangGraph-compatible graph builder
# ---------------------------------------------------------------------------

# Sentinel used in edge_map to denote the node that all fan-out branches
# converge to after completing — equivalent to LangGraph's END / join.
_AFTER = "__after__"


class PipelineGraph:
    """
    Mirrors the LangGraph StateGraph API using plain Python.

    Usage mirrors LangGraph exactly:
        g = PipelineGraph(state_schema=PipelineState)
        g.add_node("baseline", node_baseline)
        g.add_edge("baseline", "router")
        g.add_conditional_edges("router", routing_fn, {"__after__": "critic"})
        compiled = g.compile()
        result = compiled.invoke(initial_state)

    To swap in real LangGraph:
        from langgraph.graph import StateGraph
        PipelineGraph = StateGraph          # one-line swap
    """

    def __init__(self, state_schema: type) -> None:
        self._state_schema = state_schema
        self._nodes: dict[str, Callable[[PipelineState], PipelineState]] = {}
        self._edges: dict[str, str] = {}                    # from → to (unconditional)
        self._conditional: dict[str, tuple[Callable, dict[str, str]]] = {}  # from → (fn, map)
        self._entry: str | None = None
        self._finish: str | None = None

    def add_node(
        self,
        name: str,
        fn: Callable[[PipelineState], PipelineState],
    ) -> "PipelineGraph":
        """Register a node function."""
        self._nodes[name] = fn
        return self

    def set_entry_point(self, name: str) -> "PipelineGraph":
        """Set the first node to execute when the graph is invoked."""
        self._entry = name
        return self

    def set_finish_point(self, name: str) -> "PipelineGraph":
        """
        Declare the last node before END.

        In real LangGraph this is done via add_edge(name, END).
        We keep it as an explicit method so the swap stays mechanical.
        """
        self._finish = name
        return self

    def add_edge(self, from_node: str, to_node: str) -> "PipelineGraph":
        """Add an unconditional edge between two nodes."""
        self._edges[from_node] = to_node
        return self

    def add_conditional_edges(
        self,
        source: str,
        routing_fn: Callable[[PipelineState], list[str]],
        edge_map: dict[str, str],
    ) -> "PipelineGraph":
        """
        Add a conditional (fan-out) edge from source.

        routing_fn(state) must return a list of node names to execute
        in order (fan-out).  After all fan-out nodes complete, execution
        continues to edge_map["__after__"].

        In real LangGraph, fan-out uses Send() objects; here we handle it
        sequentially, which is equivalent for non-async pipelines.
        """
        self._conditional[source] = (routing_fn, edge_map)
        return self

    def compile(self) -> "CompiledGraph":
        """Validate the graph structure and return an executable CompiledGraph."""
        if self._entry is None:
            raise ValueError("No entry point set. Call set_entry_point() first.")
        for name in self._nodes:
            if (
                name not in self._edges
                and name not in self._conditional
                and name != self._finish
            ):
                logger.debug("Graph node '%s' has no outgoing edge — treated as terminal.", name)
        return CompiledGraph(self)


class CompiledGraph:
    """
    Executes the compiled pipeline graph.

    Each node is logged as it runs, giving the demo its "visible thinking" trace:
        [ElderBridge Graph] ── baseline | risk=none
        [ElderBridge Graph] ── router | agents=[FormAgent, BenefitsAgent]
        [ElderBridge Graph]   ╰─ form (fan-out)
        [ElderBridge Graph]   ╰─ benefits (fan-out)
        [ElderBridge Graph] ── critic | reviewed=2 rewrote=False
        [ElderBridge Graph] ── guardrail | result=PASS
        [ElderBridge Graph] COMPLETE | risk_flag=none evidence_items=0
    """

    def __init__(self, graph: PipelineGraph) -> None:
        self._g = graph

    def invoke(self, state: PipelineState, partial_store: dict | None = None) -> PipelineState:
        """
        Execute all nodes in topological order, following edges and conditionals.

        Args:
            state:         Initial PipelineState (created by make_initial_state()).
            partial_store: Optional dict to store intermediate state for
                           partial-result recovery on timeout.

        Returns:
            Final PipelineState with final_decision populated.
        """
        current: str | None = self._g._entry

        while current is not None:
            if current not in self._g._nodes:
                raise RuntimeError(
                    f"Graph references node '{current}' which was never registered via add_node()."
                )

            node_fn = self._g._nodes[current]
            logger.info("[ElderBridge Graph] ── %s", current)
            state = node_fn(state)

            if partial_store is not None:
                partial_store["state"] = state

            # Resolve the next node
            if current in self._g._conditional:
                routing_fn, edge_map = self._g._conditional[current]
                fan_out_nodes: list[str] = routing_fn(state)

                if fan_out_nodes:
                    for fan_node in fan_out_nodes:
                        if fan_node not in self._g._nodes:
                            logger.warning(
                                "[ElderBridge Graph] fan-out node '%s' not registered — skipping",
                                fan_node,
                            )
                            continue
                        logger.info("[ElderBridge Graph]   ╰─ %s (fan-out)", fan_node)
                        state = self._g._nodes[fan_node](state)
                        if partial_store is not None:
                            partial_store["state"] = state
                else:
                    logger.info("[ElderBridge Graph]   (no specialist agents routed)")

                current = edge_map.get(_AFTER)

            elif current in self._g._edges:
                current = self._g._edges[current]

            elif current == self._g._finish:
                # Finish point reached — done
                current = None

            else:
                # No outgoing edge and not the finish point — implicit terminal
                current = None

        logger.info(
            "[ElderBridge Graph] COMPLETE | risk_flag=%s evidence_items=%d",
            state.get("risk_flag", "unknown"),
            len(state.get("evidence_items", [])),
        )
        return state


# ---------------------------------------------------------------------------
# Specialist routing function
# ---------------------------------------------------------------------------

# Maps agent name strings (from RouterAgent) to graph node names
_AGENT_TO_NODE: dict[str, str] = {
    "BenefitsAgent": "benefits",
    "FormAgent": "form",
    "ResearchAgent": "research",
}


def _route_to_specialists(state: PipelineState) -> list[str]:
    """
    Conditional edge routing function: converts routed_agents (agent name strings)
    to graph node names for fan-out execution.

    Called by CompiledGraph.invoke() after node_router writes routed_agents.

    Args:
        state: Current PipelineState (must contain 'routed_agents').

    Returns:
        Ordered list of node names to execute in fan-out.
    """
    return [
        _AGENT_TO_NODE[agent]
        for agent in state.get("routed_agents", [])
        if agent in _AGENT_TO_NODE
    ]


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_pipeline_graph() -> CompiledGraph:
    """
    Construct and compile the ElderBridge agent pipeline graph.

    Topology:
        baseline → router → [fan-out: benefits / form / research] → critic → guardrail

    Returns:
        CompiledGraph ready to call .invoke() on.
    """
    g = PipelineGraph(state_schema=PipelineState)

    # Register all nodes
    g.add_node("baseline", node_baseline)
    g.add_node("router",   node_router)
    g.add_node("benefits", node_benefits)
    g.add_node("form",     node_form)
    g.add_node("research", node_research)
    g.add_node("critic",   node_critic)
    g.add_node("guardrail", node_guardrail)

    # Wire edges
    g.set_entry_point("baseline")
    g.add_edge("baseline", "router")

    # Conditional fan-out from router → specialist agents → converge to critic
    g.add_conditional_edges(
        source="router",
        routing_fn=_route_to_specialists,
        edge_map={_AFTER: "critic"},
    )

    g.add_edge("critic", "guardrail")
    g.set_finish_point("guardrail")

    return g.compile()


# ---------------------------------------------------------------------------
# Module-level singleton graph (built once, reused across requests)
# ---------------------------------------------------------------------------

_graph: CompiledGraph = build_pipeline_graph()


def run_graph(event: IncomingEvent, partial_store: dict | None = None) -> FinalDecision:
    """
    Public entry point: run the full agent pipeline for one event.

    Creates a fresh PipelineState, invokes the compiled graph, and returns
    the FinalDecision assembled by node_guardrail.

    Args:
        event:         Validated, redacted IncomingEvent from the API layer.
        partial_store: Optional dict for intermediate state (partial-result recovery).

    Returns:
        FinalDecision — safe to deliver to the Android client.

    Raises:
        RuntimeError: If the graph completes without setting final_decision
                      (indicates a graph wiring bug).
    """
    initial_state = make_initial_state(event)
    final_state = _graph.invoke(initial_state, partial_store=partial_store)

    decision = final_state.get("final_decision")
    if decision is None:
        raise RuntimeError(
            "Graph completed without a final_decision. "
            "Check that node_guardrail is correctly wired as the finish point."
        )
    return decision
