"""Assembles the LangGraph StateGraph for the AI IT Support Assistant.

    User Query
        |
    classify_intent  (Intent / Decision node)
        |
    conditional routing
        |-- knowledge_search   --\
        |-- ticket_lookup      ---\
        |-- ticket_creation    ----> response_generation --> END
        |-- employee_lookup   ---/
        |-- system_status     --/
        |
        `-- direct_response --> END   (chit-chat / cancellations / re-prompts)

State (employee identity, pending confirmations, ticket drafts, conversation
history) is persisted per conversation via LangGraph's in-memory checkpointer,
keyed by a per-session ``thread_id`` - no external database is used.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agent import nodes
from src.agent.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", nodes.classify_intent_node)
    graph.add_node("employee_lookup", nodes.employee_lookup_node)
    graph.add_node("knowledge_search", nodes.knowledge_search_node)
    graph.add_node("ticket_lookup", nodes.ticket_lookup_node)
    graph.add_node("ticket_creation", nodes.ticket_creation_node)
    graph.add_node("system_status", nodes.system_status_node)
    graph.add_node("response_generation", nodes.response_generation_node)
    graph.add_node("direct_response", nodes.direct_response_node)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        nodes.route_after_intent,
        {
            "employee_lookup": "employee_lookup",
            "knowledge_search": "knowledge_search",
            "ticket_lookup": "ticket_lookup",
            "ticket_creation": "ticket_creation",
            "system_status": "system_status",
            "direct_response": "direct_response",
        },
    )

    for tool_node in ("employee_lookup", "knowledge_search", "ticket_lookup", "ticket_creation", "system_status"):
        graph.add_edge(tool_node, "response_generation")

    graph.add_edge("response_generation", END)
    graph.add_edge("direct_response", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
