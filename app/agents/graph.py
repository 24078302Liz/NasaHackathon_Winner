"""Build and compile the process-wide LangGraph workflow."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import GraphState


def route_entry(state: GraphState) -> str:
    """Route comparison requests with selected IDs directly to comparison retrieval."""
    if state.get("question_type") == "compare" and len(state.get("selected_ids") or []) >= 2:
        return "retrieve_compare"
    if state.get("question_type") == "invalid":
        return "fallback_invalid"
    return "analyze_query"


def route_after_analyze(state: GraphState) -> str:
    qtype = state.get("question_type", "search")
    if qtype == "invalid":
        return "fallback_invalid"
    if qtype == "compare":
        return "retrieve_compare"
    return "retrieve"


def route_after_grade(state: GraphState) -> str:
    return (
        "generate_answer"
        if state.get("evidence_grade") == "sufficient"
        else "fallback_insufficient"
    )


def build_graph():
    g = StateGraph(GraphState)

    g.add_node("analyze_query", nodes.analyze_query)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("grade_evidence", nodes.grade_evidence)
    g.add_node("generate_answer", nodes.generate_answer)
    g.add_node("retrieve_compare", nodes.retrieve_compare)
    g.add_node("generate_comparison", nodes.generate_comparison)
    g.add_node("validate_citations", nodes.validate_citations)
    g.add_node("fallback_insufficient", nodes.fallback_insufficient)
    g.add_node("fallback_invalid", nodes.fallback_invalid)

    g.add_conditional_edges(
        START,
        route_entry,
        {
            "analyze_query": "analyze_query",
            "retrieve_compare": "retrieve_compare",
            "fallback_invalid": "fallback_invalid",
        },
    )

    g.add_conditional_edges(
        "analyze_query",
        route_after_analyze,
        {
            "retrieve": "retrieve",
            "retrieve_compare": "retrieve_compare",
            "fallback_invalid": "fallback_invalid",
        },
    )

    g.add_edge("retrieve", "grade_evidence")
    g.add_conditional_edges(
        "grade_evidence",
        route_after_grade,
        {
            "generate_answer": "generate_answer",
            "fallback_insufficient": "fallback_insufficient",
        },
    )

    g.add_edge("retrieve_compare", "generate_comparison")
    g.add_edge("generate_answer", "validate_citations")
    g.add_edge("generate_comparison", "validate_citations")

    g.add_edge("fallback_insufficient", END)
    g.add_edge("fallback_invalid", END)
    g.add_edge("validate_citations", END)

    return g.compile()


compiled_graph = build_graph()
